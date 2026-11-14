import { createRoot } from "react-dom/client";
import { ArrowDownRight, Layers3 } from "lucide-react";
import { Architecture } from "./Architecture";
import { ResearchChat } from "./ResearchChat";
import "./style.css";

function App() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="/" aria-label="FinDoc Research home">
            <span className="brand-mark"><Layers3 size={21} strokeWidth={2.1} /></span>
            FinDoc <span>Research</span>
          </a>
          <span className="top-context">NSE</span>
        </div>
      </header>
      <main className="shell">
        <section className="intro">
          <h1>Company research</h1>
          <p>Ask about company performance and trace answers back to filings and earnings calls.</p>
          <a className="source-link architecture-link" href="#architecture">How FinDoc works <ArrowDownRight size={14} /></a>
        </section>
        <ResearchChat />
        <Architecture />
      </main>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
