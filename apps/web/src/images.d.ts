// Imported images (the landing photos). Next's generated next-env.d.ts declares these too,
// but it's gitignored and only exists after a build, and CI lints before it builds.
declare module "*.webp" {
  const image: import("next/image").StaticImageData;
  export default image;
}
