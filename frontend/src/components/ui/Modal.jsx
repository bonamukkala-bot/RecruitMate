import { useEffect } from "react";
import { X } from "lucide-react";
import clsx from "clsx";

const sizes = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl"
};

export default function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  footer
}) {
  // ── Close on Escape key ──────────────────────────────────────────────────
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  // ── Prevent body scroll when open ────────────────────────────────────────
  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "unset";
    return () => { document.body.style.overflow = "unset"; };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className={clsx(
        "relative w-full glass rounded-2xl shadow-2xl animate-slide-up",
        "bg-dark-900 border border-dark-700",
        sizes[size]
      )}>
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-dark-800">
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <button
            onClick={onClose}
            className="text-dark-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-dark-800"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 max-h-[70vh] overflow-y-auto">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 p-6 border-t border-dark-800">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}