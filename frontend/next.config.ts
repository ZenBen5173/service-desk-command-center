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
    // INTERNAL_API_URL is deliberately NOT listed here. Next inlines every
    // entry in this block at build time, so naming it would compile the
    // rewrite below down to whatever the value was during `npm run build` —
    // on a hosted deploy that is the docker-compose fallback, and no runtime
    // environment variable can override a baked-in string. It is server-side
    // only, so it never needed exposing to the client anyway.
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

  // The /api/* proxy is a route handler at src/app/api/[...path]/route.ts, not
  // a rewrite. Next resolves rewrites during `next build` and freezes the
  // destination into the routes manifest, which bakes the backend address into
  // the image — fine for docker-compose, broken anywhere the address is only
  // known at run time. See that file for the full account.

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
