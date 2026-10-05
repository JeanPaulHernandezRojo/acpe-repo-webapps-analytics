import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Botón base (estilo shadcn/ui) con la paleta del portal. */

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-[0.9rem] font-semibold " +
    "transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-400",
  {
    variants: {
      variant: {
        primary: "bg-primary-500 text-white hover:bg-primary-600",
        ghost: "text-secondary-500 hover:bg-secondary-100 hover:text-primary-600",
      },
      size: {
        md: "h-11 px-5",
        sm: "h-9 px-3",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
