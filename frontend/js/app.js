const { createApp, ref, onMounted, nextTick } = Vue;
const WS_ENDPOINT = 'ws://localhost:8000/ws';

const app = createApp({
  setup() {
    const isActive = ref(false);
    let socket = null;
    let audioContext = null;
    let workletNode = null;
    let micStream = null;
    let playbackContext = null;
    let audioQueue = [];
    let isPlaying = false;

    // Toggle the assistant on/off
    const toggleAssistant = async () => {
      if (isActive.value) {
        // Turn off
        await stopAssistant();
      } else {
        // Turn on
        await startAssistant();
      }
      isActive.value = !isActive.value;
    };

    // Start the assistant: open WebSocket, get mic, and load audio worklet.
    const startAssistant = async () => {
      // Open a WebSocket connection to the backend.
      socket = new WebSocket(WS_ENDPOINT);
      socket.binaryType = "arraybuffer";
      socket.onopen = () => {
        console.log("WebSocket connected.");
      };
      socket.onmessage = handleIncomingAudio;

      // Create an AudioContext matching the desired sample rate.
      audioContext = new AudioContext({ sampleRate: 24000 });
      try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (err) {
        console.error("Error accessing microphone:", err);
        return;
      }
      const source = audioContext.createMediaStreamSource(micStream);
      
      // Load the PCM conversion worklet.
      console.log("Loading PCM conversion worklet...");
      await audioContext.audioWorklet.addModule("/ui/js/pcm16-worklet.js");
      console.log("Worklet loaded.");
      workletNode = new AudioWorkletNode(audioContext, "pcm16-processor", {
        processorOptions: {
          // Add silence detection options
          silenceDetection: true,
          silenceThreshold: 0.001, // Adjust this threshold as needed
          silenceFrames: 5 // Number of consecutive silent frames to consider as silence
        }
      });
      console.log("Worklet node created with silence detection.");

      // When the worklet produces PCM chunks, send them via WebSocket.
      workletNode.port.onmessage = (e) => {
        if (socket && socket.readyState === WebSocket.OPEN) {
          // e.data will contain an object with the audio data and a silence flag
          if (e.data.isSilent === false) {
            // Only send non-silent audio
            socket.send(e.data.buffer);
          }
        }
      };

      source.connect(workletNode);
    };

    // Stop the assistant: stop mic and close connections.
    const stopAssistant = async () => {
      if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
        micStream = null;
      }
      if (audioContext) {
        await audioContext.close();
        audioContext = null;
      }
      if (socket) {
        socket.close();
        socket = null;
      }
      
      // Clear audio queue
      audioQueue = [];
      isPlaying = false;
    };

    // Handle incoming audio chunks from the server.
    const handleIncomingAudio = (event) => {
      if (!playbackContext) {
        playbackContext = new AudioContext({ sampleRate: 24000 });
      }
      const arrayBuffer = event.data;
      // Convert the received ArrayBuffer (16-bit PCM) to a Float32Array.
      const int16Array = new Int16Array(arrayBuffer);
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        // Normalize from 16-bit integer to float in [-1, 1].
        float32Array[i] = int16Array[i] / 32767;
      }
      
      // Only create and add to queue if there are frames to process
      if (float32Array.length > 0) {
        // Create an AudioBuffer from the Float32Array.
        const audioBuffer = playbackContext.createBuffer(1, float32Array.length, 24000);
        audioBuffer.copyToChannel(float32Array, 0);
        
        // Add to queue instead of playing immediately
        audioQueue.push(audioBuffer);
        
        // Start playing if not already playing
        if (!isPlaying) {
          playNextInQueue();
        }
      } else {
        console.warn("Received empty audio data");
      }
    };

    // Play next audio buffer in queue
    const playNextInQueue = () => {
      if (audioQueue.length === 0) {
        isPlaying = false;
        return;
      }
      
      isPlaying = true;
      const buffer = audioQueue.shift();
      const source = playbackContext.createBufferSource();
      source.buffer = buffer;
      source.connect(playbackContext.destination);
      
      // When this chunk finishes, play the next one
      source.onended = playNextInQueue;
      
      source.start();
    };

    // Replace the existing playAudioBuffer function
    const playAudioBuffer = (buffer) => {
      audioQueue.push(buffer);
      if (!isPlaying) {
        playNextInQueue();
      }
    };

    return { toggleAssistant, isActive };
  }
});

app.mount('#app'); 