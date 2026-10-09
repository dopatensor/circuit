import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { Icon, type IconName } from "./Icon";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const VARIANT: Record<ButtonVariant, string> = {
  // The one main action on a screen.
  primary: "bg-accent text-ink border border-accent hover:brightness-[1.06]",
  secondary: "bg-panel text-fg border border-line2 hover:border-fg2",
  ghost: "bg-transparent text-fg2 border border-transparent hover:bg-raised hover:text-fg",
  danger: "bg-panel text-danger border border-line2 hover:border-danger",
};
// Heights: 36 (dense desktop rows, with a 44px hit area from padding around it), 44, 48.
const SIZE: Record<ButtonSize, string> = {
  sm: "min-h-9 px-3 text-sm",
  md: "min-h-11 px-4 text-base",
  lg: "min-h-12 px-5 text-base",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", extra = "") {
  return (
    "inline-flex cursor-pointer select-none items-center justify-center gap-2 rounded-lg font-semibold " +
    // Press feedback: a small scale (transform only), off with reduced motion.
    "transition-[transform,filter,background-color,border-color,color] duration-150 active:scale-[0.97] " +
    "disabled:cursor-default disabled:opacity-40 disabled:active:scale-100 " +
    `${VARIANT[variant]} ${SIZE[size]} ${extra}`
  );
}

type Common = { variant?: ButtonVariant; size?: ButtonSize; icon?: IconName; children?: ReactNode };

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  className = "",
  children,
  type = "button",
  ...props
}: Common & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type={type} className={buttonClass(variant, size, className)} {...props}>
      {icon && <Icon name={icon} size={size === "sm" ? 16 : 18} />}
      {children}
    </button>
  );
}

/** A link that looks like a button (navigation inside the app). */
export function ButtonLink({
  variant = "secondary",
  size = "md",
  icon,
  className = "",
  children,
  ...props
}: Common & LinkProps) {
  return (
    <Link className={buttonClass(variant, size, className)} {...props}>
      {icon && <Icon name={icon} size={size === "sm" ? 16 : 18} />}
      {children}
    </Link>
  );
}

/** A link to another site, styled as a button. */
export function ExternalButton({
  variant = "secondary",
  size = "md",
  icon,
  className = "",
  children,
  ...props
}: Common & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a target="_blank" rel="noreferrer" className={buttonClass(variant, size, className)} {...props}>
      {icon && <Icon name={icon} size={size === "sm" ? 16 : 18} />}
      {children}
    </a>
  );
}

/** A square button with only an icon; the label is for screen readers and tooltips. */
export function IconButton({
  icon,
  label,
  className = "",
  ...props
}: { icon: IconName; label: string } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-lg text-fg2 transition-[transform,background-color] duration-150 hover:bg-raised hover:text-fg active:scale-[0.94] ${className}`}
      {...props}
    >
      <Icon name={icon} size={22} />
    </button>
  );
}
