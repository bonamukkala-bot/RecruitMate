export default function LoadingSpinner({ size = "md", text = "" }) {
  const sizes = {
    sm: "w-4 h-4",
    md: "w-8 h-8",
    lg: "w-12 h-12"
  };

  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className={`${sizes[size]} animate-spin rounded-full border-2 border-dark-700 border-t-primary-500`} />
      {text && <p className="text-dark-400 text-sm">{text}</p>}
    </div>
  );
}