import * as React from "react";
import { cn } from "@/lib/utils";

/** Glass surface (see .glass in globals.css). Pass `interactive` for the hover glow. */
export const Card = ({ className, interactive, ...p }: React.ComponentProps<"div"> & { interactive?: boolean }) => (
  <div className={cn("glass rounded-2xl text-card-foreground", interactive && "glass-hover", className)} {...p} />
);
export const CardHeader = ({ className, ...p }: React.ComponentProps<"div">) => <div className={cn("flex flex-col gap-1 p-5 pb-3", className)} {...p} />;
export const CardTitle = ({ className, ...p }: React.ComponentProps<"h2">) => <h2 className={cn("text-sm font-semibold tracking-tight", className)} {...p} />;
export const CardDescription = ({ className, ...p }: React.ComponentProps<"p">) => <p className={cn("text-sm text-muted-foreground", className)} {...p} />;
export const CardContent = ({ className, ...p }: React.ComponentProps<"div">) => <div className={cn("p-5 pt-0", className)} {...p} />;
