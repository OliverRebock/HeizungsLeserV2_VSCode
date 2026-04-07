import React from 'react';

interface LogoProps {
  className?: string;
  iconOnly?: boolean;
  variant?: 'light' | 'dark';
}

const Logo: React.FC<LogoProps> = ({ className = "h-12", iconOnly = false, variant = 'dark' }) => {
  const textColor = variant === 'light' ? '#ffffff' : '#1e293b';
  
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <svg 
        viewBox="0 0 60 60" 
        fill="none" 
        xmlns="http://www.w3.org/2000/svg"
        className="h-full w-auto drop-shadow-sm"
      >
        <defs>
          <linearGradient id="logo-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
        </defs>
        
        {/* Modern Flame / Bar Chart Hybrid */}
        <rect x="14" y="28" width="8" height="20" rx="4" fill="url(#logo-gradient)" />
        <rect x="26" y="12" width="8" height="36" rx="4" fill="url(#logo-gradient)" fillOpacity="0.8" />
        <rect x="38" y="22" width="8" height="26" rx="4" fill="url(#logo-gradient)" fillOpacity="0.6" />
        
        {/* Gauge / Measurement Arc */}
        <path 
          d="M8 44C8 50.6274 13.3726 56 20 56H40C46.6274 56 52 50.6274 52 44" 
          stroke="url(#logo-gradient)" 
          strokeWidth="4" 
          strokeLinecap="round" 
        />
      </svg>
      
      {!iconOnly && (
        <span 
          className="text-[1.2em] font-medium tracking-tight whitespace-nowrap"
          style={{ color: textColor }}
        >
          Heizungs<span className="font-extrabold">leser</span>
        </span>
      )}
    </div>
  );
};

export default Logo;
