import { clerkMiddleware } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'

const ADMIN_IDS = (process.env.ADMIN_USER_IDS ?? '')
  .split(',')
  .map(s => s.trim())
  .filter(Boolean)

export default clerkMiddleware(async (auth, request) => {
  if (request.nextUrl.pathname.startsWith('/admin')) {
    const { userId } = await auth()
    if (!userId || !ADMIN_IDS.includes(userId)) {
      return NextResponse.redirect(new URL('/', request.url))
    }
  }
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
