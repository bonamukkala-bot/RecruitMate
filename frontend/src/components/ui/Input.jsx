import clsx from "clsx";

export default function Input({
  label,
  error,
  icon: Icon,
  className = "",
  ...props
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-dark-300">
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-400">
            <Icon size={16} />
          </div>
        )}
        <input
          className={clsx(
            "input",
            Icon && "pl-10",
            error && "border-red-500 focus:border-red-500 focus:ring-red-500",
            className
          )}
          {...props}
        />
      </div>
      {error && (
        <p className="text-red-400 text-xs">{error}</p>
      )}
    </div>
  );
}