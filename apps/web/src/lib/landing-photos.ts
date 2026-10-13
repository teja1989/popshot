// Photos for the landing page's strip, served from public/landing/. Each is free to use
// (Unsplash or Pexels licence) and was approved before it went in; the source is kept here
// so the credit and licence can be checked later.
export interface LandingPhoto {
  src: string;
  alt: string;
  source: string;
}

export const LANDING_PHOTOS: LandingPhoto[] = [];
