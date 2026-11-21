// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// Mock Web Speech API for test environment
if (typeof window !== 'undefined') {
  window.speechSynthesis = {
    cancel: jest.fn(),
    speak: jest.fn((utt) => {
      if (utt && utt.onend) setTimeout(utt.onend, 10);
    }),
    getVoices: jest.fn().mockReturnValue([])
  };
  window.SpeechSynthesisUtterance = function (text) {
    this.text = text;
  };
}

// Mock ML libraries for Node test environment
jest.mock('@vladmandic/face-api', () => ({
  nets: {
    tinyFaceDetector: { loadFromUri: jest.fn().mockResolvedValue(true) },
    faceLandmark68Net: { loadFromUri: jest.fn().mockResolvedValue(true) },
    faceRecognitionNet: { loadFromUri: jest.fn().mockResolvedValue(true) }
  },
  TinyFaceDetectorOptions: jest.fn(),
  detectAllFaces: jest.fn().mockResolvedValue([]),
  detectSingleFace: jest.fn().mockReturnValue({
    withFaceLandmarks: jest.fn().mockReturnValue({
      withFaceDescriptor: jest.fn().mockResolvedValue(null)
    })
  }),
  euclideanDistance: jest.fn().mockReturnValue(0.2)
}));

jest.mock('@tensorflow-models/coco-ssd', () => ({
  load: jest.fn().mockResolvedValue({
    detect: jest.fn().mockResolvedValue([])
  })
}));

jest.mock('@tensorflow/tfjs', () => ({
  ready: jest.fn().mockResolvedValue(true)
}));
