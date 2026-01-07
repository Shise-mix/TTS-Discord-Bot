use pyo3::prelude::*;
use pyo3::types::PyBytes;
use hound::{WavReader, SampleFormat}; // WavSpec を削除
use std::io::Cursor;

// Discordの1フレームあたりのバイト数
const DISCORD_FRAME_SIZE: usize = 3840;

/// 内部ヘルパー: デシベル(dB)を振幅倍率に変換する
fn db_to_amplitude(db: f32) -> f32 {
    10.0f32.powf(db / 20.0)
}

/// 統合オーディオ処理パイプライン
/// Wavファイルのバイト列を受け取り、Trim -> Gain -> Reverb -> Discord PCM変換 を一括で行う
#[pyfunction]
fn process_audio_pipeline(
    py: Python,
    wav_bytes: &[u8],
    gain_db: f32,
    silence_threshold: i16,
    reverb_enabled: bool,
    reverb_delay_ms: u32,
    reverb_decay: f32,
    reverb_mix: f32,
) -> PyResult<Py<PyAny>> { // PyObject -> Py<PyAny> に更新
    // 1. メモリ上のWavデータを読み込む
    let cursor = Cursor::new(wav_bytes);
    let mut reader = WavReader::new(cursor)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Wav read error: {}", e)))?;
    
    let spec = reader.spec();
    let channels = spec.channels as usize;
    let sample_rate = spec.sample_rate;
    
    // サンプルをf32としてすべて読み込む (mut を削除)
    let samples: Vec<f32> = match spec.sample_format {
        SampleFormat::Int => {
            reader.samples::<i16>().map(|s| s.unwrap_or(0) as f32).collect()
        },
        SampleFormat::Float => {
            reader.samples::<f32>().map(|s| s.unwrap_or(0.0)).collect()
        }
    };

    if samples.is_empty() {
        return Ok(PyBytes::new(py, &[]).into());
    }

    // --- 2. Trim Silence (無音カット) ---
    // ステレオ対応の簡易トリミング
    let threshold = silence_threshold.abs() as f32;
    let mut start_index = 0;
    while start_index < samples.len() {
        // 全チャンネルが閾値以下なら無音とみなす
        let mut is_silence = true;
        for c in 0..channels {
            if start_index + c < samples.len() && samples[start_index + c].abs() > threshold {
                is_silence = false; 
                break;
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
             if samples[check_start + c].abs() > threshold { 
                 is_silence = false; 
                 break; 
             }
        }
        if !is_silence { break; }
        end_index -= channels;
    }
    
    // スライスして新しいVecにする（必要部分のみ抽出）
    let mut processed_samples = samples[start_index..end_index].to_vec();
    
    // フェードアウト処理 (末尾20ms)
    let fade_samples = ((sample_rate as f32 * 0.02) as usize) * channels;
    let len = processed_samples.len();
    if len > fade_samples {
        let fade_start = len - fade_samples;
        for i in 0..fade_samples {
            let gain = 1.0 - (i as f32 / fade_samples as f32);
            let idx = fade_start + i;
            if idx < len {
                processed_samples[idx] *= gain;
            }
        }
    }

    // --- 3. Apply Gain (音量調整) ---
    let amp = db_to_amplitude(gain_db);
    for s in &mut processed_samples {
        *s *= amp;
    }

    // --- 4. Apply Reverb (リバーブ) ---
    if reverb_enabled {
        let delay_samples = ((sample_rate as f32 * reverb_delay_ms as f32) / 1000.0) as usize;
        // チャンネルごとのリングバッファ
        let mut buffers: Vec<Vec<f32>> = vec![vec![0.0; delay_samples]; channels];
        let mut buf_indices = vec![0; channels];

        for i in 0..processed_samples.len() {
            let ch = i % channels;
            let input_val = processed_samples[i];
            
            let delayed_val = buffers[ch][buf_indices[ch]];
            let reverb_val = input_val + (delayed_val * reverb_decay);
            
            // バッファ更新
            buffers[ch][buf_indices[ch]] = reverb_val;
            buf_indices[ch] = (buf_indices[ch] + 1) % delay_samples;
            
            // Mix
            processed_samples[i] = (input_val * (1.0 - reverb_mix)) + (reverb_val * reverb_mix);
        }
    }

    // --- 5. Resample & Format to Discord PCM (48kHz Stereo 16bit) ---
    let dst_rate = 48000;
    let ratio = sample_rate as f32 / dst_rate as f32;
    let src_frames = processed_samples.len() / channels;
    let dst_frames = (src_frames as f32 / ratio).ceil() as usize;
    
    // 出力バッファ (L, R, L, R...)
    let mut output_bytes = Vec::with_capacity(dst_frames * 4 + 48000); // 少し余裕を持つ

    for i in 0..dst_frames {
        let src_idx_float = i as f32 * ratio;
        let src_idx_floor = src_idx_float.floor() as usize;
        let t = src_idx_float - src_idx_floor as f32;

        if src_idx_floor + 1 >= src_frames { break; }

        // 線形補間
        let (l_val, r_val) = if channels == 1 {
            let p0 = processed_samples[src_idx_floor];
            let p1 = processed_samples[src_idx_floor + 1];
            let val = p0 + (p1 - p0) * t;
            (val, val) // モノラル -> ステレオ複製
        } else {
            let p0_l = processed_samples[src_idx_floor * 2];
            let p1_l = processed_samples[(src_idx_floor + 1) * 2];
            let val_l = p0_l + (p1_l - p0_l) * t;

            let p0_r = processed_samples[src_idx_floor * 2 + 1];
            let p1_r = processed_samples[(src_idx_floor + 1) * 2 + 1];
            let val_r = p0_r + (p1_r - p0_r) * t;
            (val_l, val_r)
        };

        // i16変換 & リトルエンディアン書き込み
        for val in [l_val, r_val] {
            let clamped = val.max(i16::MIN as f32).min(i16::MAX as f32) as i16;
            output_bytes.extend_from_slice(&clamped.to_le_bytes());
        }
    }

    // --- 6. Padding & Alignment ---
    // 0.5秒のパディング
    let padding_size = 48000 * 2 * 2 / 2; // 不要な括弧を削除
    output_bytes.extend(std::iter::repeat(0).take(padding_size));

    // アライメント調整 (Discordフレームサイズに合わせる)
    let remainder = output_bytes.len() % DISCORD_FRAME_SIZE;
    if remainder != 0 {
        let align_padding = DISCORD_FRAME_SIZE - remainder;
        output_bytes.extend(std::iter::repeat(0).take(align_padding));
    }

    Ok(PyBytes::new(py, &output_bytes).into())
}

#[pymodule]
fn rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(process_audio_pipeline, m)?)?;
    Ok(())
}