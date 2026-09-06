import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Gaia — A living AI companion',
  description:
    'Een interactieve frontend voor Gaia: jouw levende persoonlijke AI-companion.',
  openGraph: {
    title: 'Gaia — A living AI companion',
    description: 'Een rustige, levende AI-interface die begrijpt, onthoudt en handelt.',
    type: 'website',
    locale: 'nl_NL',
    images: [{ url: '/og.png', width: 1731, height: 909, alt: 'Gaia, een levende AI-companion' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Gaia — A living AI companion',
    description: 'Een rustige, levende AI-interface die begrijpt, onthoudt en handelt.',
    images: ['/og.png'],
  },
};

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#07080f',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="nl">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <template
          aria-hidden="true"
          dangerouslySetInnerHTML={{
            __html: `<!--
THESIS: Gaia is a living companion and a mission-control surface for autonomous work; it refuses both the generic AI transcript and the dense admin dashboard.
OWN-WORLD: A nocturnal cobalt-black spatial canvas, pearl-violet companion light, mint signals, breathing orthogonal particles, continuous Apple-like geometry, and frost reserved for navigation and command islands.
STORY: Per begins in a personal Today command center, sees the active mission, end goal, progress, ETA and approvals, then enters a distinct Chat, Work cockpit or persistent Memory space.
FIRST VIEWPORT: A centered frosted space switcher crowns a living lattice; a fully visible Gaia occupies the open spatial center while one mission surface and two attention requests orbit it, and a compact command dock replaces the full composer outside Chat.
FORM: Spatial companion observatory, grounded direction 7, seed 4fb3b735.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
-->`,
          }}
        />
        {children}
      </body>
    </html>
  );
}
