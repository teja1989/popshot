// Photos on the landing page, bundled from src/components/landing/photos/ (WebP, 800 and
// 1600 wide, metadata stripped). Both are free to use under the Unsplash License, chosen by
// Popshot's owner. No faces: people show only from far above. Brand logos and model names
// on the paddle were removed, so it doesn't read as an endorsement.
export interface LandingPhoto {
  alt: string;
  source: string;
}

export const COURT_AERIAL: LandingPhoto = {
  alt: "A doubles game on a blue pickleball court, seen from directly above.",
  source: "Unsplash (Unsplash License)",
};

export const PADDLE_AND_BALLS: LandingPhoto = {
  alt: "A red pickleball paddle resting on yellow balls by the net.",
  source: "Unsplash (Unsplash License), logos removed",
};
