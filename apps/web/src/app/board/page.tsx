import { permanentRedirect } from "next/navigation";

// The Board became the Crew tab; old links and home-screen shortcuts still land there.
export default function BoardPage() {
  permanentRedirect("/crew");
}
