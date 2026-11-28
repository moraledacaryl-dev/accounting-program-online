/** @type {import('next').NextConfig} */
const path = require('path');

const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
  { key: 'Strict-Transport-Security', value: 'max-age=31536000' },
];

const nextConfig = {
  reactStrictMode: true,
  ...(process.env.NEXT_PUBLIC_ACCOUNTING_TRAINING==='1'?{output:'standalone'}:{}),
  async rewrites(){return process.env.NEXT_PUBLIC_ACCOUNTING_TRAINING==='1'?[{source:'/api/:path*',destination:'http://127.0.0.1:8420/api/:path*'}]:[];},
  poweredByHeader: false,
  outputFileTracingRoot: path.join(__dirname),
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
    ];
  },
};
module.exports = nextConfig;
