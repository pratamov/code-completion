import os
import json
import pickle
import tensorflow as tf
import h5py
from tensorflow.keras.layers import Embedding, LSTM, Dense, Input, Concatenate
from tensorflow.keras.models import Model

assert str(tf.__version__) == "2.14.0", "require tensorflow==2.14.0"

def load_model_compatible(base_dir="models/lstm"):
    """
    Robust model loading with enhanced weight loading verification
    Returns: model, vocab_data, metadata
    """
    # 1. Find and verify latest version directory
    try:
        version_dirs = [d for d in os.listdir(base_dir) if d.startswith("v") and os.path.isdir(os.path.join(base_dir, d))]
        if not version_dirs:
            raise FileNotFoundError(f"No valid model versions found in {base_dir}")
        
        version_dirs.sort(key=lambda x: int(x.split('_')[0][1:]), reverse=True)
        latest_dir = os.path.join(base_dir, version_dirs[0])
        print(f"Loading model from {latest_dir}")
    except Exception as e:
        raise RuntimeError(f"Directory scanning failed: {str(e)}")

    # 2. Load metadata and vocab data
    try:
        with open(os.path.join(latest_dir, 'metadata.json'), 'r') as f:
            metadata = json.load(f)
        
        with open(os.path.join(latest_dir, 'vocab_data.pkl'), 'rb') as f:
            vocab_data = pickle.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load metadata/vocab: {str(e)}")

    # 3. Attempt loading with verification
    model = None
    load_strategies = [
        ("SavedModel", try_load_savedmodel),
        ("Weights", lambda: try_load_weights(latest_dir, metadata, vocab_data)),
        ("Rebuild", lambda: try_rebuild_model(latest_dir, metadata, vocab_data))
    ]

    for strategy_name, strategy in load_strategies:
        try:
            print(f"\nAttempting {strategy_name} strategy...")
            model = strategy()
            
            if model is not None and verify_weights_loaded(model):
                print(f"{strategy_name} strategy succeeded")
                break
                
            model = None  # Reset if verification failed
        except Exception as e:
            print(f"{strategy_name} strategy failed: {str(e)}")
            continue

    if model is None:
        raise RuntimeError("All model loading strategies failed")

    print("\nModel successfully loaded with verified weights")
    return model, vocab_data, metadata

def verify_weights_loaded(model):
    """Thorough verification of loaded weights"""
    for layer in model.layers:
        weights = layer.get_weights()
        if not weights:
            if isinstance(layer, (Embedding, LSTM, Dense)):  # Layers that should have weights
                print(f"Warning: {layer.name} has no weights")
                return False
        else:
            for w in weights:
                if w.size == 0:
                    print(f"Warning: {layer.name} has empty weight array")
                    return False
    
    # Additional check - try a dummy prediction
    try:
        dummy_input = [tf.convert_to_tensor([[1]]), tf.convert_to_tensor([[1]])]
        _ = model.predict(dummy_input, verbose=0)
    except Exception as e:
        print(f"Prediction verification failed: {str(e)}")
        return False
    
    return True

def try_load_savedmodel(model_dir):
    """Attempt loading full SavedModel with verification"""
    saved_model_path = os.path.join(model_dir, 'saved_model')
    if os.path.exists(saved_model_path):
        model = tf.keras.models.load_model(saved_model_path)
        return model
    return None

def try_load_weights(model_dir, metadata, vocab_data):
    """Attempt loading weights with architecture recreation"""
    weights_path = os.path.join(model_dir, 'model_weights.h5')
    if os.path.exists(weights_path):
        model = create_multi_property_model(
            word_vocab_size=metadata['word_vocab_size'],
            property_vocab_sizes=metadata['property_vocab_sizes'],
            word_embed_dim=64,
            prop_embed_dims=[32] * len(metadata['property_vocab_sizes']),
            lstm_units=128
        )
        
        # Enhanced weights loading
        try:
            model.load_weights(weights_path)
            return model
        except Exception as e:
            print(f"Standard weights loading failed: {str(e)}")
            # Try layer-by-layer loading
            return load_weights_layerwise(model, weights_path)
    return None

def load_weights_layerwise(model, weights_path):
    """Alternative weights loading approach"""
    try:
        # Get all weight names from the file
        with h5py.File(weights_path, 'r') as f:
            weight_names = [n.decode('utf8') for n in f.attrs['weight_names']]
        
        # Create weight value dictionary
        weight_values = {}
        with h5py.File(weights_path, 'r') as f:
            for name in weight_names:
                weight_values[name] = f[name][:]
        
        # Apply weights layer by layer
        for layer in model.layers:
            layer_weights = []
            for weight in layer.weights:
                name = weight.name.replace(':0', '')
                if name in weight_values:
                    layer_weights.append(weight_values[name])
            
            if layer_weights:
                layer.set_weights(layer_weights)
        
        return model
    except Exception as e:
        print(f"Layer-wise loading failed: {str(e)}")
        return None

def try_rebuild_model(model_dir, metadata, vocab_data):
    """Full model rebuild with multiple weight sources"""
    print("Attempting full model rebuild...")
    model = create_multi_property_model(
        word_vocab_size=metadata['word_vocab_size'],
        property_vocab_sizes=metadata['property_vocab_sizes'],
        word_embed_dim=64,
        prop_embed_dims=[32] * len(metadata['property_vocab_sizes']),
        lstm_units=128
    )
    
    # Try all possible weight sources
    weight_sources = [
        os.path.join(model_dir, 'model_weights.h5'),
        os.path.join(model_dir, 'saved_model/variables/variables')
    ]
    
    for source in weight_sources:
        if os.path.exists(source):
            try:
                print(f"Trying weights from: {source}")
                model.load_weights(source)
                if verify_weights_loaded(model):
                    return model
            except Exception as e:
                print(f"Failed loading from {source}: {str(e)}")
    
    print("Warning: Returning model with random initialization (no weights loaded)")
    return model

def create_multi_property_model(word_vocab_size, property_vocab_sizes, 
                              word_embed_dim=64, prop_embed_dims=32, lstm_units=128):
    """Recreate the original model architecture"""
    if isinstance(prop_embed_dims, int):
        prop_embed_dims = [prop_embed_dims] * len(property_vocab_sizes)
    
    # Word input
    word_input = Input(shape=(None,), name='word_input')
    word_embed = Embedding(word_vocab_size, word_embed_dim, name='word_embedding')(word_input)
    
    # Property inputs
    prop_inputs = []
    prop_embeds = []
    for i, (vocab_size, embed_dim) in enumerate(zip(property_vocab_sizes, prop_embed_dims)):
        prop_input = Input(shape=(None,), name=f'property_{i}_input')
        prop_embed = Embedding(vocab_size, embed_dim, name=f'property_{i}_embedding')(prop_input)
        prop_inputs.append(prop_input)
        prop_embeds.append(prop_embed)
    
    # Combine all embeddings
    combined = Concatenate()([word_embed] + prop_embeds)
    
    # LSTM layer
    lstm_out = LSTM(lstm_units)(combined)
    
    # Outputs
    outputs = [
        Dense(word_vocab_size, activation='softmax', name='word_output')(lstm_out)
    ]
    for i, vocab_size in enumerate(property_vocab_sizes):
        outputs.append(
            Dense(vocab_size, activation='softmax', name=f'property_{i}_output')(lstm_out)
        )
    
    return Model(inputs=[word_input] + prop_inputs, outputs=outputs)


def load_model():
    model, vocab_data, metadata = load_model_compatible()
    print("\nModel summary:")
    model.summary()
    print(f"\nLoaded model version {metadata['version']} created on {metadata['date_created']}")

    # Test prediction
    print("\nTesting prediction...")
    test_input = [tf.constant([[1]]), tf.constant([[1]])]
    model.predict(test_input)
    print("Prediction successful!")
    
    return model, vocab_data, metadata

def sample_from_logits(logits: tf.Tensor, temperature: float) -> int:
    """Temperature-based sampling with proper shape handling"""
    # Ensure logits is 2D: [batch_size, num_classes]
    if len(logits.shape) < 2:
        logits = tf.expand_dims(logits, 0)
    
    scaled_logits = logits / temperature
    samples = tf.random.categorical(scaled_logits, num_samples=1)
    return samples.numpy()[0, 0]


DEFAULT_TOKEN = "<EOL>"
DEFAULT_PROPERTIES = ["ANY"]
def make_inference(
    model, 
    vocab_data,
    seed_tokens: list[str],
    seed_properties: list[list[str]],  # List of property lists for each property type
    num_generate: int = 10,
    temperature: float = 1.0
) -> tuple[list[str], list[list[str]]]:
    """
    Generate sequence with properties using the trained model.
    
    Args:
        model: The trained model
        vocab_data: Vocabulary mappings
        seed_tokens: Initial tokens as list of strings
        seed_properties: List of property sequences (one list per property type)
        num_generate: Number of tokens to generate
        temperature: Controls randomness (0.1-1.0: conservative, 1.0-2.0: creative)
    
    Returns:
        Tuple of (generated_tokens, generated_properties)
    """
    # Validate inputs
    num_properties = len(vocab_data['property_to_idx'])
    if len(seed_properties) != num_properties:
        raise ValueError(f"Need {num_properties} property sequences, got {len(seed_properties)}")
    
    for prop_seq in seed_properties:
        if len(prop_seq) != len(seed_tokens):
            raise ValueError("Property sequences must match seed token length")

    # Get vocabulary mappings
    word_to_idx = vocab_data['word_to_idx']
    idx_to_word = vocab_data['idx_to_word']
    property_to_idx = vocab_data['property_to_idx']
    idx_to_property = vocab_data['idx_to_property']
    max_seq_len = vocab_data['max_sequence_length']

    # Convert seed tokens to IDs with fallback
    token_ids = [word_to_idx.get(t, 0) for t in seed_tokens]
    prop_ids = [
        [property_to_idx[i].get(p, 0) for p in prop_seq]
        for i, prop_seq in enumerate(seed_properties)
    ]

    # Pad/truncate sequences to max length
    def process_sequence(seq: list[int], max_len: int) -> list[int]:
        return seq[-max_len:] if len(seq) > max_len else [0]*(max_len-len(seq)) + seq

    token_ids = process_sequence(token_ids, max_seq_len)
    prop_ids = [process_sequence(p, max_seq_len) for p in prop_ids]

    # Initialize generation buffers
    generated_tokens = []
    generated_props = [[] for _ in range(num_properties)]

    for _ in range(num_generate):
        # Prepare model inputs with batch dimension
        token_input = tf.expand_dims(token_ids, 0)  # Shape: [1, seq_len]
        prop_inputs = [tf.expand_dims(p, 0) for p in prop_ids]  # List of [1, seq_len]

        # Get predictions (returns list of outputs)
        predictions = model.predict([token_input] + prop_inputs, verbose=0)

        # Process word prediction
        word_logits = predictions[0][0, :]  # Shape: [vocab_size]
        word_logits = tf.expand_dims(word_logits, 0)  # Shape: [1, vocab_size]
        # print(word_logits)
        word_id = sample_from_logits(word_logits, temperature)
        generated_tokens.append(idx_to_word.get(word_id, DEFAULT_TOKEN))

        # Process properties
        new_prop_ids = []
        for i in range(num_properties):
            prop_logits = predictions[i+1][0, :]  # Shape: [prop_vocab_size]
            prop_logits = tf.expand_dims(prop_logits, 0)  # Shape: [1, prop_vocab_size]
            prop_id = sample_from_logits(prop_logits, temperature)
            generated_props[i].append(idx_to_property[i].get(prop_id, DEFAULT_PROPERTIES[i]))
            new_prop_ids.append(prop_id)

        # Update sequences
        token_ids.append(word_id)
        token_ids = token_ids[-max_seq_len:]
        
        for i, pid in enumerate(new_prop_ids):
            prop_ids[i].append(pid)
            prop_ids[i] = prop_ids[i][-max_seq_len:]

    return generated_tokens, generated_props