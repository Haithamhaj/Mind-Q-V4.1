/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/mindq/:path*',
        destination: 'http://127.0.0.1:9000/:path*',
      },
      {
        source: '/api/bi/:path*',
        destination: 'http://127.0.0.1:9000/api/bi/:path*',
      },
    ]
  },
}

export default nextConfig