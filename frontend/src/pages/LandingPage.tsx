import React from 'react';
import { ArrowRight, FileText, Search, CheckCircle, ShieldCheck } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

interface LandingPageProps {
  onOpenWorkspace: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onOpenWorkspace }) => {
  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px 0 60px 0' }}>
      {/* Hero Section */}
      <div style={{ textAlign: 'center', marginBottom: '56px' }}>
        {/* Eyebrow badge */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 16px',
            borderRadius: 'var(--r-pill)',
            background: 'var(--surface-soft)',
            boxShadow: 'var(--raise-1)',
            border: '1px solid var(--hairline)',
            fontSize: '12px',
            fontWeight: 700,
            color: 'var(--blue-action)',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            marginBottom: '24px',
          }}
        >
          ResearchMind AI · Week 1 Foundation
        </div>

        {/* Two-tone headline */}
        <h1
          style={{
            fontSize: 'clamp(2.5rem, 5vw, 3.75rem)',
            fontWeight: 800,
            lineHeight: 1.1,
            letterSpacing: '-0.03em',
            marginBottom: '16px',
          }}
        >
          <span style={{ color: 'var(--text-primary)' }}>Evidence-First. </span>
          <span style={{ color: 'var(--gray-400)' }}>Research Analysis.</span>
        </h1>

        {/* Apple Cadence Tagline */}
        <div
          style={{
            fontSize: '18px',
            fontWeight: 600,
            color: 'var(--text-primary)',
            letterSpacing: '-0.01em',
            marginBottom: '16px',
          }}
        >
          Traceable. Grounded. Verified.
        </div>

        {/* Lede */}
        <p
          style={{
            maxWidth: '640px',
            margin: '0 auto 36px auto',
            fontSize: '17px',
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
          }}
        >
          Analyze academic research papers with page-level citations, hybrid semantic search,
          and strict evidence grounding. Built for local-first privacy and honest scientific inquiry.
        </p>

        {/* Action Pill CTA */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <Button
            variant="ink"
            size="lg"
            onClick={onOpenWorkspace}
            style={{ padding: '12px 32px', fontSize: '16px' }}
          >
            <span>Open Workspace</span>
            <ArrowRight size={18} />
          </Button>
        </div>
      </div>

      {/* Feature Capsule Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '20px',
          marginBottom: '56px',
        }}
      >
        <Card elevation={1} style={{ textAlign: 'left', borderRadius: 'var(--r-xl)' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: 'var(--r-md)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--blue-action)',
              marginBottom: '16px',
            }}
          >
            <FileText size={22} />
          </div>
          <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Universal Ingestion</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Accepts any text-based PDF without subject restriction. Validates headers, sizes, and integrity.
          </p>
        </Card>

        <Card elevation={1} style={{ textAlign: 'left', borderRadius: 'var(--r-xl)' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: 'var(--r-md)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--green-strong)',
              marginBottom: '16px',
            }}
          >
            <Search size={22} />
          </div>
          <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Hybrid Retrieval</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Combines all-MiniLM dense vectors with BM25 keyword matching via Reciprocal Rank Fusion.
          </p>
        </Card>

        <Card elevation={1} style={{ textAlign: 'left', borderRadius: 'var(--r-xl)' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: 'var(--r-md)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--orange-strong)',
              marginBottom: '16px',
            }}
          >
            <CheckCircle size={22} />
          </div>
          <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Page-Level Citations</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Every statement maps directly to source page numbers with coordinate-level highlighting.
          </p>
        </Card>

        <Card elevation={1} style={{ textAlign: 'left', borderRadius: 'var(--r-xl)' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: 'var(--r-md)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--ink)',
              marginBottom: '16px',
            }}
          >
            <ShieldCheck size={22} />
          </div>
          <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Strict Abstention</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Explicitly informs you when evidence is missing rather than generating unverified assertions.
          </p>
        </Card>
      </div>

      {/* Privacy Notice Banner */}
      <Card
        variant="sunken"
        style={{
          padding: '20px 28px',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          borderRadius: 'var(--r-lg)',
        }}
      >
        <ShieldCheck size={24} color="var(--green-strong)" style={{ flexShrink: 0 }} />
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong>Local-First Guarantee:</strong> Your original research papers, extracted text, and embedding indexes remain private inside your local <code>data/</code> directory.
        </div>
      </Card>
    </div>
  );
};
