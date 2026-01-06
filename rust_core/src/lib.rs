use pyo3::prelude::*;
use pyo3::types::PyBytes;
use hound::{WavReader, WavWriter, SampleFormat};
use std::cmp::max;

// Discordの1フレームあたりのバイト数
// 48000Hz * 2ch * 2bytes(16bit) * 0.02s(20ms) = 3840 bytes
const DISCORD_FRAME_SIZE: usize = 3840;

/// 内部ヘルパー: デシベル(dB)を振幅倍率に変換する
fn db_to_amplitude(db: f32) -> f32 {
    10.0f32.powf(db / 20.0)
}

// --- 既存関数群 ---

#[pyfunction]
fn apply_gain(input_path: &str, output_path: &str, gain_db: f32) -> PyResult<()> {
    let mut reader = WavReader::open(input_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Read error: {}", e)))?;
    let spec = reader.spec();
    let mut writer = WavWriter::create(output_path, spec)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Write error: {}", e)))?;
    let amp = db_to_amplitude(gain_db);
    for sample in reader.samples::<i16>() {
        let s = sample.unwrap_or(0);
        let val = s as f32 * amp;
        let clamped = val.max(i16::MIN as f32).min(i16::MAX as f32);
        writer.write_sample(clamped as i16).unwrap();
    }
    writer.finalize().unwrap();
    Ok(())
}

#[pyfunction]
fn trim_silence(input_path: &str, output_path: &str, threshold_level: i16) -> PyResult<()> {
    let mut reader = WavReader::open(input_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Read error: {}", e)))?;
    let spec = reader.spec();
    let channels = spec.channels as usize;
    let samples: Vec<i16> = reader.samples::<i16>().map(|s| s.unwrap_or(0)).collect();
    
    if samples.is_empty() {
        let writer = WavWriter::create(output_path, spec)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Write error: {}", e)))?;
        writer.finalize().unwrap();
        return Ok(());
    }

    let threshold = threshold_level.abs();
    let mut start_index = 0;
    while start_index < samples.len() {
        let mut is_silence = true;
        for c in 0..channels {
            if start_index + c < samples.len() && samples[start_index + c].abs() > threshold {
                is_silence = false; break;
            }
        }
        if !is_silence { break; }
        start_index += channels;
    }

    let mut end_index = samples.len();
    while end_index > start_index {
        let mut is_silence = true;
        let check_start = end_index - channels;
        for c in 0..channels {
             if samples[check_start + c].abs() > threshold { is_silence = false; break; }
        }
        if !is_silence { break; }
        end_index -= channels;
    }

    let mut writer = WavWriter::create(output_path, spec)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Write error: {}", e)))?;

    // フェードアウト処理 (20ms)
    let fade_ms = 20.0;
    let fade_samples = ((spec.sample_rate as f32 * fade_ms) / 1000.0) as usize * channels;
    let total_len = end_index - start_index;
    let fade_start_pos = if total_len > fade_samples { total_len - fade_samples } else { 0 };

    for (pos, i) in (start_index..end_index).enumerate() {
        let mut val = samples[i] as f32;
        if pos >= fade_start_pos && fade_samples > 0 {
            let remaining = total_len - pos;
            let gain = remaining as f32 / fade_samples as f32;
            val *= gain;
        }
        writer.write_sample(val as i16).unwrap();
    }
    writer.finalize().unwrap();
    Ok(())
}

#[pyfunction]
fn apply_reverb(input_path: &str, output_path: &str, delay_ms: u32, decay: f32, mix: f32) -> PyResult<()> {
    let mut reader = WavReader::open(input_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Read error: {}", e)))?;
    let spec = reader.spec();
    let channels = spec.channels as usize;
    let sample_rate = spec.sample_rate;
    let mut writer = WavWriter::create(output_path, spec)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Write error: {}", e)))?;

    let delay_samples = ((sample_rate as f32 * delay_ms as f32) / 1000.0) as usize;
    let mut buffers: Vec<Vec<f32>> = vec![vec![0.0; delay_samples]; channels];
    let mut buf_indices = vec![0; channels];

    for (i, sample) in reader.samples::<i16>().map(|s| s.unwrap_or(0)).enumerate() {
        let ch = i % channels;
        let input_val = sample as f32;
        let delayed_val = buffers[ch][buf_indices[ch]];
        let reverb_val = input_val + (delayed_val * decay);
        buffers[ch][buf_indices[ch]] = reverb_val;
        buf_indices[ch] = (buf_indices[ch] + 1) % delay_samples;
        let out_val = (input_val * (1.0 - mix)) + (reverb_val * mix);
        let clamped = out_val.max(i16::MIN as f32).min(i16::MAX as f32);
        writer.write_sample(clamped as i16).unwrap();
    }
    writer.finalize().unwrap();
    Ok(())
}

#[pyfunction]
fn mix_wavs(base_path: &str, overlay_path: &str, output_path: &str, delay_ms: u32, base_vol: f32, overlay_vol: f32) -> PyResult<()> {
    let mut reader1 = WavReader::open(base_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Base read error: {}", e)))?;
    let spec = reader1.spec();
    let channels = spec.channels as usize;
    let samples1: Vec<i16> = reader1.samples::<i16>().map(|s| s.unwrap_or(0)).collect();

    let mut reader2 = WavReader::open(overlay_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Overlay read error: {}", e)))?;
    let samples2: Vec<i16> = reader2.samples::<i16>().map(|s| s.unwrap_or(0)).collect();

    let delay_samples = ((spec.sample_rate as f32 * delay_ms as f32 / 1000.0) as usize) * channels;
    let len1 = samples1.len();
    let len2 = samples2.len() + delay_samples;
    let max_len = max(len1, len2);

    let mut writer = WavWriter::create(output_path, spec)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Write error: {}", e)))?;

    for i in 0..max_len {
        let val1 = if i < len1 { samples1[i] as f32 * base_vol } else { 0.0 };
        let val2 = if i >= delay_samples && (i - delay_samples) < samples2.len() {
            samples2[i - delay_samples] as f32 * overlay_vol
        } else { 0.0 };
        let mixed = val1 + val2;
        let clamped = mixed.max(i16::MIN as f32).min(i16::MAX as f32);
        writer.write_sample(clamped as i16).unwrap();
    }
    writer.finalize().unwrap();
    Ok(())
}

// --- 修正箇所: アライメント調整を追加 ---

#[pyfunction]
fn load_pcm_data(py: Python, input_path: &str) -> PyResult<PyObject> {
    let mut reader = WavReader::open(input_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Read error: {}", e)))?;
    let spec = reader.spec();
    let src_channels = spec.channels as usize;
    let src_rate = spec.sample_rate;
    
    let samples: Vec<f32> = match spec.sample_format {
        SampleFormat::Int => {
            reader.samples::<i16>().map(|s| s.unwrap_or(0) as f32).collect()
        },
        SampleFormat::Float => {
            reader.samples::<f32>().map(|s| s.unwrap_or(0.0)).collect()
        }
    };

    let dst_rate = 48000;
    let ratio = src_rate as f32 / dst_rate as f32;
    let src_frames = samples.len() / src_channels;
    let dst_frames = (src_frames as f32 / ratio).ceil() as usize;
    
    // バッファ確保
    let mut output_bytes = Vec::with_capacity(dst_frames * 4 + 96000);

    for i in 0..dst_frames {
        let src_idx_float = i as f32 * ratio;
        let src_idx_floor = src_idx_float.floor() as usize;
        let t = src_idx_float - src_idx_floor as f32;

        if src_idx_floor + 1 >= src_frames { break; }

        let (l_sample, r_sample) = if src_channels == 1 {
            let p0 = samples[src_idx_floor];
            let p1 = samples[src_idx_floor + 1];
            let val = p0 + (p1 - p0) * t;
            (val, val)
        } else {
            let p0_l = samples[src_idx_floor * 2];
            let p1_l = samples[(src_idx_floor + 1) * 2];
            let val_l = p0_l + (p1_l - p0_l) * t;

            let p0_r = samples[src_idx_floor * 2 + 1];
            let p1_r = samples[(src_idx_floor + 1) * 2 + 1];
            let val_r = p0_r + (p1_r - p0_r) * t;
            (val_l, val_r)
        };

        for val in [l_sample, r_sample] {
            let clamped = val.max(i16::MIN as f32).min(i16::MAX as f32) as i16;
            output_bytes.extend_from_slice(&clamped.to_le_bytes());
        }
    }

    // 1. パディング（無音）の追加 (0.5秒)
    let padding_size = (48000.0 * 0.5 * 2.0 * 2.0) as usize; 
    output_bytes.extend(vec![0u8; padding_size]);

    // 2. ★アライメント調整: データ長を 3840 (20ms) の倍数にする
    // 半端なデータがあるとOpusエンコーダが不正な終端処理を行いノイズの原因になる
    let remainder = output_bytes.len() % DISCORD_FRAME_SIZE;
    if remainder != 0 {
        let align_padding = DISCORD_FRAME_SIZE - remainder;
        output_bytes.extend(vec![0u8; align_padding]);
    }

    Ok(PyBytes::new(py, &output_bytes).into())
}

#[pymodule]
fn rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(apply_gain, m)?)?;
    m.add_function(wrap_pyfunction!(trim_silence, m)?)?;
    m.add_function(wrap_pyfunction!(apply_reverb, m)?)?;
    m.add_function(wrap_pyfunction!(mix_wavs, m)?)?;
    m.add_function(wrap_pyfunction!(load_pcm_data, m)?)?;
    Ok(())
}