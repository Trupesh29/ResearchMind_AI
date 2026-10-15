import React from 'react';
import {
  FileText,
  CheckCircle,
  AlertTriangle,
  Clock,
  ArrowRight,
  Database,
  Cpu,
  HardDrive,
  Bot,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ReadyResponse, PublicConfigResponse } from '../api/types';

interface DashboardPageProps {
  onNavigateToLibrary: () => void;
  readyStatus: 'online' | 'degraded' | 'offline' | 'loading';
  readyData: ReadyResponse | null;
  configData: PublicConfigResponse | null;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onNavigateToLibrary,
  readyStatus,
  readyData,
  configData,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Header Row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '28px', marginBottom: '6px' }}>Workspace Dashboard</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
            Overview of uploaded research documents, processing statuses, and system foundation.
          </p>
        </div>

        <Button variant="ink" onClick={onNavigateToLibrary}>
          <span>Open Library</span>
          <ArrowRight size={16} />
        </Button>
      </div>

      {/* Metric KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
        }}
      >
        <Card elevation={1}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>Total Papers</span>
            <FileText size={18} color="var(--blue-action)" />
          </div>
          <div className="tabular-nums" style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)' }}>
            0
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Awaiting Phase 2 uploads
          </div>
        </Card>

        <Card elevation={1}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>Ready for Search</span>
            <CheckCircle size={18} color="var(--green-strong)" />
          </div>
          <div className="tabular-nums" style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)' }}>
            0
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Indexed with FAISS & BM25
          </div>
        </Card>

        <Card elevation={1}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>In Processing</span>
            <Clock size={18} color="var(--orange-strong)" />
          </div>
          <div className="tabular-nums" style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)' }}>
            0
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Active extraction jobs
          </div>
        </Card>

        <Card elevation={1}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>Quality Flagged</span>
            <AlertTriangle size={18} color="var(--gray-500)" />
          </div>
          <div className="tabular-nums" style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)' }}>
            0
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Scans / unread tables
          </div>
        </Card>
      </div>

      {/* System Foundation & Environment Verification Panel */}
      <Card elevation={2}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '18px', marginBottom: '4px' }}>System Architecture & Environment</h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Live runtime status verified via FastAPI <code>/api/ready</code> probe.
            </p>
          </div>
          <Badge
            variant={readyStatus === 'online' ? 'success' : readyStatus === 'loading' ? 'info' : 'error'}
          >
            {readyStatus === 'online' ? 'System Operational' : readyStatus === 'loading' ? 'Probing...' : 'Offline'}
          </Badge>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
          }}
        >
          {/* Database Block */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--r-lg)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Database size={16} color="var(--blue-action)" />
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>Database</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <div><strong>Engine:</strong> SQLite (WAL + Foreign Keys)</div>
              <div><strong>Status:</strong> {readyData?.checks.database || 'Connecting...'}</div>
              <div><strong>Migrations:</strong> Alembic Initial Schema</div>
            </div>
          </div>

          {/* Storage Block */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--r-lg)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <HardDrive size={16} color="var(--green-strong)" />
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>Private Storage</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <div><strong>Directory:</strong> <code>data/</code></div>
              <div><strong>Write Permission:</strong> {readyData?.checks.storage || 'Checking...'}</div>
              <div><strong>Max Upload:</strong> {configData?.max_upload_mb || 25} MB</div>
            </div>
          </div>

          {/* Machine Learning Block */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--r-lg)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Cpu size={16} color="var(--orange-strong)" />
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>ML Embedder</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <div><strong>Model:</strong> all-MiniLM-L6-v2</div>
              <div><strong>Dimension:</strong> 384 vectors</div>
              <div><strong>FAISS:</strong> CPU Fallback Ready</div>
            </div>
          </div>

          {/* Generator Provider Block */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--r-lg)',
              background: 'var(--surface-sunken)',
              boxShadow: 'var(--inset-1)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Bot size={16} color="var(--ink)" />
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>Generator</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <div><strong>Provider:</strong> {readyData?.checks.generator.provider || 'mock'}</div>
              <div><strong>Model:</strong> {readyData?.checks.generator.model || 'gpt-4o-mini'}</div>
              <div><strong>Status:</strong> {readyData?.checks.generator.status || 'Active'}</div>
            </div>
          </div>
        </div>
      </Card>

      {/* Build Roadmap Progress Panel */}
      <Card elevation={1}>
        <h2 style={{ fontSize: '18px', marginBottom: '16px' }}>Build Sequence & Readiness</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--r-md)', background: 'var(--surface-soft)' }}>
            <div>
              <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>Week 1 Phase 1: Project Foundation & App Shell</strong>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>FastAPI backend, SQLite/Alembic, models, Apple Modern design tokens, ML smoke check.</div>
            </div>
            <Badge variant="success">Completed</Badge>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--r-md)', background: 'var(--surface)' }}>
            <div>
              <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>Week 1 Phase 2: PDF Library & Multi-file Upload Lifecycle</strong>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Drag-and-drop uploads, %PDF- magic bytes check, SHA-256 deduplication, original PDF viewer.</div>
            </div>
            <Badge variant="info">Next Phase</Badge>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--r-md)', background: 'var(--surface)' }}>
            <div>
              <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>Week 2: Universal Extraction & Quality Center</strong>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>PyMuPDF page block extraction, 200-token chunking, scan/table detection flags.</div>
            </div>
            <Badge variant="neutral">Upcoming</Badge>
          </div>
        </div>
      </Card>
    </div>
  );
};
