import clsx from "clsx";
import LoadingSpinner from "./LoadingSpinner";

const variants = {
  primary  : "btn-primary",
  secondary: "btn-secondary",
  danger   : "btn-danger",
  ghost    : "btn-ghost"
};

const sizes = {
  sm: "text-xs px-3 py-1.5",
  md: "text-sm px-4 py-2",
  lg: "text-base px-5 py-2.5"
};

export default function Button({
  children, variant = "primary", size = "md",
  loading = false, disabled = false,
  className = "", onClick, type = "button", ...props
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={clsx(variants[variant], sizes[size], className)}
      {...props}
    >
      {loading
        ? <><LoadingSpinner size="sm" /><span>Loading...</span></>
        : children
      }
    </button>
  );
}