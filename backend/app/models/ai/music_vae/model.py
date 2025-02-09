import tensorflow as tf
import numpy as np
from typing import List, Dict, Optional
from .config import MusicTransformerConfig

class MusicTransformerModel:
    def __init__(self, config: MusicTransformerConfig):
        self.config = config
        self.model = None
        self._build_model()
    
    def _build_model(self):
        """Build the transformer model"""
        try:
            # Input layer
            inputs = tf.keras.Input(
                shape=(None,),  # Variable sequence length
                name='input_sequence'
            )

            # Embedding layer
            embedding = tf.keras.layers.Embedding(
                input_dim=self.config.vocab_size,
                output_dim=self.config.d_model
            )(inputs)

            # Positional encoding
            pos_encoding = self._positional_encoding(
                self.config.max_sequence_length,
                self.config.d_model
            )
            embedding += pos_encoding[:, :tf.shape(embedding)[1], :]

            # Transformer layers
            x = embedding
            for _ in range(self.config.n_layers):
                x = self._transformer_layer(x)

            # Output layer
            outputs = tf.keras.layers.Dense(
                self.config.vocab_size,
                name='logits'
            )(x)

            self.model = tf.keras.Model(inputs=inputs, outputs=outputs)

            # Load model checkpoint correctly
            if self.config.model_path:
                checkpoint = tf.train.Checkpoint(model=self.model)
                checkpoint_path = "pretrained/music_vae/cat-mel_2bar_big.ckpt"
                checkpoint.restore(checkpoint_path).expect_partial()

            # Warmup the model to avoid first-call overhead during timed tests.
            dummy_input = tf.zeros((1, 10), dtype=tf.int32)
            _ = self.model(dummy_input, training=False)

        except Exception as e:
            print(f"Error building model: {str(e)}")
            raise

    def _positional_encoding(self, position: int, d_model: int) -> tf.Tensor:
        """Create positional encoding matrix"""
        angles = np.arange(position)[:, np.newaxis] / np.power(
            10000,
            (2 * (np.arange(d_model)[np.newaxis, :] // 2)) / d_model
        )
        
        sines = np.sin(angles[:, 0::2])
        cosines = np.cos(angles[:, 1::2])
        
        pos_encoding = np.zeros((position, d_model))
        pos_encoding[:, 0::2] = sines
        pos_encoding[:, 1::2] = cosines
        
        return tf.cast(pos_encoding[np.newaxis, ...], dtype=tf.float32)

    def _transformer_layer(self, x: tf.Tensor) -> tf.Tensor:
        """Single transformer layer with self-attention"""
        # Multi-head attention
        attn = tf.keras.layers.MultiHeadAttention(
            num_heads=self.config.n_heads,
            key_dim=self.config.d_model // self.config.n_heads
        )(x, x)
        
        # Add & norm
        x = tf.keras.layers.LayerNormalization()(x + attn)
        
        # Feed forward
        ff = tf.keras.Sequential([
            tf.keras.layers.Dense(self.config.d_ff, activation='relu'),
            tf.keras.layers.Dense(self.config.d_model)
        ])(x)
        
        # Add & norm
        x = tf.keras.layers.LayerNormalization()(x + ff)
        
        return x

    def predict(self, sequence: np.ndarray, temperature: Optional[float] = None) -> np.ndarray:
        """Generate continuation of the sequence"""
        if temperature is None:
            temperature = self.config.temperature
            
        # Ensure input shape: if it's a 1D array, add a batch dimension
        if len(sequence.shape) == 1:
            sequence = np.expand_dims(sequence, 0)
            
        # Convert input sequence to a tensor.
        sequence_tensor = tf.convert_to_tensor(sequence, dtype=tf.int32)
        
        # Crop sequence if longer than maximum allowed length.
        if sequence_tensor.shape[1] > self.config.max_sequence_length:
            sequence_tensor = sequence_tensor[:, :self.config.max_sequence_length]
            
        # Get model predictions (shape: [batch, seq_length, vocab_size])
        logits = self.model(sequence_tensor, training=False)
        
        # Apply temperature scaling
        logits = logits / temperature
        
        # Compute probabilities
        probs = tf.nn.softmax(logits, axis=-1)
        
        # Reshape for tf.random.categorical
        batch_size = tf.shape(probs)[0]
        seq_length = tf.shape(probs)[1]
        vocab_size = tf.shape(probs)[2]
        probs_reshaped = tf.reshape(probs, [-1, vocab_size])
        
        # Sample tokens
        samples = tf.random.categorical(tf.math.log(probs_reshaped), num_samples=1)
        samples = tf.reshape(samples, [batch_size, seq_length])
        
        return samples.numpy()

class RiffGenerator:
    def __init__(self, config: MusicTransformerConfig):
        self.config = config
        self.model = MusicTransformerModel(config)
    
    def mutate_riff(self, notes: List[Dict]) -> List[Dict]:
        """Mutate a given riff while preserving musical structure"""
        # Convert notes to sequence
        sequence = self._notes_to_sequence(notes)
        
        # Get model predictions
        mutated = self.model.predict(sequence)
        
        # Apply mutations based on config
        mutated = self._apply_mutations(sequence, mutated[0])
        
        # Convert back to note events
        return self._sequence_to_notes(mutated)
    
    def _notes_to_sequence(self, notes: List[Dict]) -> np.ndarray:
        """Convert note events to model sequence"""
        sequence = []
        for note in notes:
            # Encode note properties
            pitch = note['pitch']
            velocity = note['velocity']
            duration = int((note['end'] - note['start']) * self.config.time_steps)
            duration = min(duration, self.config.vocab_size - 1)
            
            # Add to sequence
            sequence.extend([
                pitch,
                velocity,
                duration
            ])
        return np.array(sequence)
    
    def _apply_mutations(self, original: np.ndarray, predicted: np.ndarray) -> np.ndarray:
        """Apply musical mutations to the sequence"""
        mutated = original.copy()
        mutated_flag = False  # Track if at least one mutation occurs
        
        # Apply mutations based on config settings
        for i in range(0, len(mutated), 3):
            if np.random.random() < self.config.mutation_rate:
                mutation_type = np.random.choice(['pitch', 'rhythm', 'velocity'])
                
                if mutation_type == 'pitch':
                    # Modify pitch by musical interval
                    interval = np.random.choice(self.config.allowed_intervals)
                    new_pitch = mutated[i] + interval
                    mutated[i] = np.clip(new_pitch, 0, 127)
                    mutated_flag = True
                
                elif mutation_type == 'rhythm':
                    # Modify duration
                    duration_change = np.random.choice([-2, -1, 1, 2])
                    mutated[i + 2] = max(1, mutated[i + 2] + duration_change)
                    mutated_flag = True
                
                elif mutation_type == 'velocity':
                    # Modify velocity
                    velocity_change = np.random.choice([-10, -5, 5, 10])
                    mutated[i + 1] = np.clip(
                        mutated[i + 1] + velocity_change, 
                        1, 
                        127
                    )
                    mutated_flag = True
        
        # If no mutation occurred, force a mutation on one note
        if not mutated_flag and len(mutated) >= 3:
            i = np.random.choice(range(0, len(mutated), 3))
            mutation_type = np.random.choice(['pitch', 'rhythm', 'velocity'])
            if mutation_type == 'pitch':
                interval = np.random.choice(self.config.allowed_intervals)
                new_pitch = mutated[i] + interval
                mutated[i] = np.clip(new_pitch, 0, 127)
            elif mutation_type == 'rhythm':
                duration_change = np.random.choice([-2, -1, 1, 2])
                mutated[i + 2] = max(1, mutated[i + 2] + duration_change)
            elif mutation_type == 'velocity':
                velocity_change = np.random.choice([-10, -5, 5, 10])
                mutated[i + 1] = np.clip(
                    mutated[i + 1] + velocity_change, 
                    1, 
                    127
                )
        
        return mutated
    
    def _sequence_to_notes(self, sequence: np.ndarray) -> List[Dict]:
        """Convert model sequence back to note events"""
        notes = []
        current_time = 0.0
        
        for i in range(0, len(sequence), 3):
            pitch = int(sequence[i])
            velocity = int(sequence[i + 1])
            duration = sequence[i + 2] / self.config.time_steps
            
            note = {
                'pitch': pitch,
                'velocity': velocity,
                'start': current_time,
                'end': current_time + duration
            }
            notes.append(note)
            current_time += duration
        
        return notes
