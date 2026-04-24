import React from 'react';
import { Card } from '../common/Card';
import { BriefingViewer } from './BriefingViewer';

export const AIBriefing: React.FC = () => {
  return (
    <Card title="AI Daily Briefing">
      <BriefingViewer />
    </Card>
  );
};
