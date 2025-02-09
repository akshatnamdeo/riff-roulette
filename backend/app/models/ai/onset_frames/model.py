import tensorflow as tf
import numpy as np
from typing import Tuple, Optional
from .config import OnsetFramesConfig

class OnsetFramesModel:
    def __init__(self, config: OnsetFramesConfig):
        """Initialize the Onset & Frames model"""
        self.config = config
        self.model = None
        self._build_model()
    
    def _build_model(self):
        """Build the model architecture and load weights using the object-based API"""
        try:
            # Build the model architecture. Make sure it matches the saved architecture.
            inputs = tf.keras.Input(shape=(None, self.config.n_mels), name='mel_input')
            
            # Onset detection branch
            onset_conv = tf.keras.layers.Conv1D(64, 3, padding='same', name='onset_conv')(inputs)
            onset_bn = tf.keras.layers.BatchNormalization(name='onset_bn')(onset_conv)
            onset_relu = tf.keras.layers.ReLU(name='onset_relu')(onset_bn)
            onset_dense = tf.keras.layers.Dense(88, activation='sigmoid', name='onset_probs')(onset_relu)
            
            # Frame detection branch
            frame_conv = tf.keras.layers.Conv1D(64, 3, padding='same', name='frame_conv')(inputs)
            frame_bn = tf.keras.layers.BatchNormalization(name='frame_bn')(frame_conv)
            frame_relu = tf.keras.layers.ReLU(name='frame_relu')(frame_bn)
            frame_dense = tf.keras.layers.Dense(88, activation='sigmoid', name='frame_probs')(frame_relu)
            
            outputs = [onset_dense, frame_dense]
            self.model = tf.keras.Model(inputs=inputs, outputs=outputs, name='onsets_frames')
            
            # Use the object-based checkpoint API to load weights.
            # Create a Checkpoint object with your model.
            ckpt = tf.train.Checkpoint(model=self.model)
            # Restore the checkpoint. Note: self.config.model_path should be the prefix.
            status = ckpt.restore(self.config.model_path)
            # If you expect a partial restoration, call:
            status.expect_partial()
            # Alternatively, if you expect a complete match, you can use:
            # status.assert_existing_objects_matched()
        except Exception as e:
            print(f"Error building model: {str(e)}")
            raise
    
    def predict(self, mel_spectrogram: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Generate onset and frame predictions"""
        if self.model is None:
            raise RuntimeError("Model not initialized")
            
        if len(mel_spectrogram.shape) == 2:
            mel_spectrogram = np.expand_dims(mel_spectrogram, 0)
            
        onset_probs, frame_probs = self.model.predict(mel_spectrogram, verbose=0)
        return onset_probs, frame_probs

class AudioProcessor:
    def __init__(self, config: OnsetFramesConfig):
        self.config = config

    def preprocess_audio(self, audio: np.ndarray) -> np.ndarray:
        """Convert audio to mel spectrograms for model input"""
        import librosa
        
        # If audio is 2D (e.g., (1, length)), convert to 1D
        if len(audio.shape) == 2:
            audio = audio.flatten()
        
        mel_spec = librosa.feature.melspectrogram(
            y=audio,
            sr=self.config.sample_rate,
            n_mels=self.config.n_mels,
            hop_length=self.config.hop_length,
            n_fft=2048,
            fmin=self.config.fmin,
            fmax=self.config.fmax
        )
        mel_spec = librosa.power_to_db(mel_spec, ref=np.max)
        mel_spec = (mel_spec - mel_spec.mean()) / (mel_spec.std() + 1e-6)
        mel_spec = mel_spec.T  # (time, n_mels)
        mel_spec = np.expand_dims(mel_spec, 0)  # (1, time, n_mels)
        return mel_spec

    def process_predictions(self, onset_pred: np.ndarray, frame_pred: np.ndarray,
                            min_duration: Optional[float] = 0.05) -> list:
        """Convert model predictions to note events"""
        note_events = []
        active_pitches = {}
        time_per_frame = self.config.hop_length / self.config.sample_rate
        
        for frame_idx in range(len(onset_pred)):
            frame_time = frame_idx * time_per_frame
            for pitch in range(88):
                is_onset = onset_pred[frame_idx, pitch] > self.config.onset_threshold
                is_active = frame_pred[frame_idx, pitch] > self.config.frame_threshold
                
                if is_onset and is_active and pitch not in active_pitches:
                    active_pitches[pitch] = {
                        'start': frame_time,
                        'pitch': pitch + 21,  # MIDI pitch
                        'velocity': int(min(127, frame_pred[frame_idx, pitch] * 127))
                    }
                elif pitch in active_pitches and not is_active:
                    note = active_pitches[pitch]
                    duration = frame_time - note['start']
                    if duration >= min_duration:
                        note['end'] = frame_time
                        note_events.append(note.copy())
                    del active_pitches[pitch]
        
        final_time = len(onset_pred) * time_per_frame
        for pitch, note in active_pitches.items():
            note['end'] = final_time
            note_events.append(note.copy())
        
        return note_events
