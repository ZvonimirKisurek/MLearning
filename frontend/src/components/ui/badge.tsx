import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap", {
  variants: {
    variant: {
      default: "border-transparent bg-muted text-muted-foreground",
      outline: "text-muted-foreground",
      primary: "border-primary/30 bg-primary/10 text-primary",
      info: "border-info/30 bg-info/10 text-info",
      warn: "border-warn/30 bg-warn/10 text-warn",
      violet: "border-violet/30 bg-violet/10 text-violet",
    },
  },
  defaultVariants: { variant: "default" },
});

export function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
