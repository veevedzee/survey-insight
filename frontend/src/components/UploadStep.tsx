import { useRef, useState, type DragEvent } from "react";

interface Props {
  busy: boolean;
  onFile: (file: File) => void;
  onSample: () => void;
}

const ACCEPTED = [".csv", ".xlsx"];

export function UploadStep({ busy, onFile, onSample }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  function pick(file: File | undefined) {
    if (!file) return;
    const ok = ACCEPTED.some((ext) => file.name.toLowerCase().endsWith(ext));
    if (!ok) {
      setLocalError("Please choose a .csv or .xlsx file.");
      return;
    }
    setLocalError(null);
    onFile(file);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files[0]);
  }

  return (
    <section className="upload">
      <div className="hero">
        <h2>Turn a raw survey export into findings you can defend.</h2>
        <p className="muted">
          Upload a Google Forms or Microsoft Forms export. You'll get cleaned data, the right
          statistical tests, and themes from open-ended answers in English and Arabic.
        </p>
      </div>

      <label
        className={`dropzone${dragging ? " dropzone-active" : ""}${busy ? " dropzone-busy" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="visually-hidden"
          disabled={busy}
          onChange={(e) => pick(e.target.files?.[0])}
        />
        <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true" className="dropzone-icon">
          <path
            d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <strong>{busy ? "Reading your file…" : "Drop your survey file here"}</strong>
        <span className="muted">or click to browse · CSV or XLSX · up to 10 MB</span>
      </label>

      {localError && <p className="error-text">{localError}</p>}

      <div className="upload-actions">
        <span className="muted">No file handy?</span>
        <button type="button" className="button button-secondary" onClick={onSample} disabled={busy}>
          Try with sample data
        </button>
      </div>

      <ul className="trust">
        <li>
          <strong>Processed in memory</strong>
          <span>Your file is never written to disk and is forgotten after 30 minutes.</span>
        </li>
        <li>
          <strong>Personal data removed first</strong>
          <span>Names, emails, phone numbers and IDs are stripped before any analysis.</span>
        </li>
        <li>
          <strong>No paid AI</strong>
          <span>Open-source statistics and language models, explained step by step.</span>
        </li>
      </ul>
    </section>
  );
}
