import tensorflow as tf
import numpy as np

# Create simple anomaly detection model
model = tf.keras.Sequential([
    tf.keras.layers.Dense(8, activation='relu', input_shape=(2,)),
    tf.keras.layers.Dense(4, activation='relu'),
    tf.keras.layers.Dense(1, activation='sigmoid')
])

model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

# TODO: Add training data and train model
# model.fit(X_train, y_train, epochs=100)

# Convert to TFLite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

# Save model
with open('dht_anomaly_model.tflite', 'wb') as f:
    f.write(tflite_model)

print("Model converted to TFLite successfully!")
