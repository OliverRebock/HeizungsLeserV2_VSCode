import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import DeviceChatPanel from './components/DeviceChatPanel';

const DeviceChatPage: React.FC = () => {
  const { deviceId } = useParams<{ deviceId: string }>();

  if (!deviceId) {
    return (
      <div className="p-6 bg-white border border-slate-200 rounded-xl text-slate-600">
        Ungueltige Geraete-ID.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">KI-Einsatz-Chat</h1>
        <Link
          to={`/devices/${deviceId}`}
          className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-slate-200 hover:bg-slate-50"
        >
          <ArrowLeft className="w-4 h-4" /> Zurueck zum Geraet
        </Link>
      </div>
      <DeviceChatPanel deviceId={deviceId} />
    </div>
  );
};

export default DeviceChatPage;
