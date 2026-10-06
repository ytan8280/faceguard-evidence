export default function GuidePage() {
  return (
    <main className="page">
      <section className="panel">
        <h2>How FaceGuard Works</h2>
        <p className="panel-note">
          FaceGuard leverages a sophisticated Vision Transformer (ViT) model, a neural network architecture that has
          achieved state-of-the-art results in computer vision tasks. Here’s a step-by-step guide to how it protects
          your digital identity.
        </p>
        <ol className="guide-list">
          <li>
            <strong>Image Upload:</strong> Navigate to the Detector page and upload an image. We support common formats
            like JPEG, PNG, and WebP for your convenience.
          </li>
          <li>
            <strong>Privacy-First Preprocessing:</strong> Before analysis, we automatically strip all EXIF metadata from
            your image. The file is then converted to a standardized format in-memory, ensuring no personal data is
            retained.
          </li>
          <li>
            <strong>AI-Powered Analysis:</strong> The processed image is passed to our fine-tuned Vision Transformer
            model, which analyzes the image for subtle artifacts and inconsistencies that are often invisible to the
            human eye but are characteristic of AI-generated content.
          </li>
          <li>
            <strong>Instant Verdict:</strong> Based on the model's analysis, you receive a clear "REAL" or "FAKE"
            verdict, along with a confidence score that indicates the model's certainty in its conclusion.
          </li>
        </ol>
        <p className="panel-note">
          This entire process happens locally in your browser and our backend server. No images are ever stored or
          logged, upholding our commitment to your privacy.
        </p>
      </section>
    </main>
  );
}

