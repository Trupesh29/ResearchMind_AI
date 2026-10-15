import React from 'react';
import { Home } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

interface NotFoundPageProps {
  onGoHome: () => void;
}

export const NotFoundPage: React.FC<NotFoundPageProps> = ({ onGoHome }) => {
  return (
    <div style={{ maxWidth: '480px', margin: '60px auto', textAlign: 'center' }}>
      <Card elevation={2}>
        <div
          style={{
            fontSize: '72px',
            fontWeight: 800,
            color: 'var(--gray-400)',
            lineHeight: 1,
            marginBottom: '16px',
            fontFamily: 'var(--font-mono)',
          }}
        >
          404
        </div>
        <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Page Not Found</h2>
        <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '24px' }}>
          The requested route does not exist in this workspace navigation.
        </p>
        <Button variant="ink" onClick={onGoHome}>
          <Home size={16} />
          <span>Return to Dashboard</span>
        </Button>
      </Card>
    </div>
  );
};
