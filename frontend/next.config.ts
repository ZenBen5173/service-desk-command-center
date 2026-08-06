import type { NextConfig } from 'next'

// Handle basePath - Next.js requires either empty string or path starting with /
// but NOT just "/" alone
const getBasePath = () => {
  const path = process.env.NEXT_PUBLIC_BASE_PATH || ''
  // "/" is not a valid basePath, treat it as empty
  if (path === '/') return ''
  return path
}

const nextConfig: NextConfig = {
  basePath: getBasePath(),

  env: {
    // `??`, not `||`. An empty value is a deliberate choice meaning "same
    // origin", and `||` treated it as unset and substituted localhost — so any
    // browser that was not on this machine called its own localhost:8001 and
    // every panel rendered empty.
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001',
    INTERNAL_API_URL: process.env.INTERNAL_API_URL || 'http://backend:8000',
  },
  serverExternalPackages: [],

  // Tree-shake heavy icon/component libraries
  experimental: {
    optimizePackageImports: [
      '@radix-ui/react-icons',
      'lucide-react',
      'recharts',
      'framer-motion',
    ],
  },

  // Ensure TypeScript errors fail the build
  typescript: {
    ignoreBuildErrors: false,
  },

  // Disable source maps in production for faster builds
  productionBrowserSourceMaps: false,

  // Proxy API calls to the backend from this same origin.
  //
  // Without this the browser has to reach the backend on its own host and port,
  // which means two public URLs and a CORS allowlist when the app is shared
  // outside this machine. One origin is simpler and is what a reviewer expects
  // from a single link.
  //
  // /api/auth/* is excluded explicitly rather than relying on route precedence.
  // `afterFiles` did not reliably yield to the App Router's auth handlers here,
  // and the proxy swallowed NextAuth's session endpoint — which surfaced as
  // every page rendering empty while the API was healthy. A negative lookahead
  // is unambiguous.
  async rewrites() {
    const backend = process.env.INTERNAL_API_URL || 'http://backend:8000'
    return {
      beforeFiles: [],
      afterFiles: [
        {
          source: '/api/:path((?!auth/).*)',
          destination: `${backend}/api/:path*`,
        },
      ],
      fallback: [],
    }
  },

  // Windows bind mounts into the Docker Linux VM do not deliver inotify events,
  // so the dev server never notices an edit and every change needs a container
  // restart. Polling is the only thing that works there. Opt in explicitly via
  // WATCHPACK_POLLING so native Linux/macOS development keeps event-based
  // watching, which is much cheaper on CPU.
  webpack: (config, { dev }) => {
    if (dev && process.env.WATCHPACK_POLLING === 'true') {
      config.watchOptions = {
        ...config.watchOptions,
        poll: 1000,
        aggregateTimeout: 300,
        ignored: ['**/node_modules/**', '**/.next/**', '**/.git/**'],
      }
    }
    return config
  },
}

export default nextConfig
