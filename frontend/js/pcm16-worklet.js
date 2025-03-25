class PCM16Processor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    // Get silence detection options from processor options
    const processorOptions = options.processorOptions || {};
    this.silenceDetection = processorOptions.silenceDetection || false;
    this.silenceThreshold = processorOptions.silenceThreshold || 0.01;
    this.silenceFrames = processorOptions.silenceFrames || 10;
    this.silentCount = 0;
    this.isSilent = true;
  }

  process(inputs, outputs) {
    // Get the input audio data (we only use the first channel of the first input).
    const input = inputs[0][0];
    if (!input) return true;

    // Create an Int16Array to convert the float audio to 16-bit PCM.
    const pcm16 = new Int16Array(input.length);
    
    // Check if the audio is silent
    let isSilent = true;
    let maxAmplitude = 0;
    
    // Convert floating point audio (-1.0 to 1.0) to 16-bit PCM (-32768 to 32767).
    for (let i = 0; i < input.length; i++) {
      // Clip the signal to [-1, 1]
      const sample = Math.max(-1, Math.min(1, input[i]));
      // Convert to 16-bit PCM
      pcm16[i] = Math.round(sample * 32767);
      
      // For silence detection, track absolute amplitude
      const absAmp = Math.abs(sample);
      maxAmplitude = Math.max(maxAmplitude, absAmp);
    }
    
    // Determine if this buffer is silent
    const currentBufferIsSilent = maxAmplitude < this.silenceThreshold;
    
    if (this.silenceDetection) {
      // Update silence counter
      if (currentBufferIsSilent) {
        this.silentCount++;
      } else {
        this.silentCount = 0;
      }
      
      // Determine overall silence state
      this.isSilent = this.silentCount >= this.silenceFrames;
    } else {
      this.isSilent = false;
    }
    
    // Send the PCM data to the main thread, along with silence info
    this.port.postMessage({
      buffer: pcm16.buffer,
      isSilent: this.isSilent
    }, [pcm16.buffer]);
    
    return true;
  }
}

registerProcessor('pcm16-processor', PCM16Processor);
  