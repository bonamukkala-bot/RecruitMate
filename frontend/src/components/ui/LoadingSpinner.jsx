export default function LoadingSpinner({ size = "md", text = "" }) {
  const sizes = { sm: "w-4 h-4", md: "w-7 h-7", lg: "w-10 h-10" };
  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className={`${sizes[size]} animate-spin rounded-full border-2 border-gray-200 border-t-indigo-600`} />
      {text && <p className="text-gray-400 text-sm font-medium">{text}</p>}
    </div>
  );
}