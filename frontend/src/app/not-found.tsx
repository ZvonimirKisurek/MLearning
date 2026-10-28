import Link from "next/link";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="glass mx-auto max-w-md rounded-2xl p-8 text-center">
      <Compass className="mx-auto mb-3 size-7 text-muted-foreground" />
      <h2 className="text-lg font-semibold">Nothing here</h2>
      <p className="mt-1 text-sm text-muted-foreground">That task does not exist, or it was regenerated. Go back to today&apos;s mission.</p>
      <Button asChild className="mt-5"><Link href="/">Today&apos;s mission</Link></Button>
    </div>
  );
}
