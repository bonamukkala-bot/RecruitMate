import { useState } from "react";
import Button from "../ui/Button";
import { RotateCcw, Save, AlertCircle } from "lucide-react";

export default function SettingsSection({
  title,
  description,
  badge,
  isDirty = false,
  loading = false,
  error = null,
  onSave,
  onReset,
  children
}) {
  const [resetConfirming, setResetConfirming] = useState(false);

  const handleResetClick = () => {
    if (resetConfirming) {
      setResetConfirming(false);
      if (onReset) onReset();
    } else {
      setResetConfirming(true);
      setTimeout(() => setResetConfirming(false), 4000);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-stone-200 shadow-card overflow-hidden transition-all">
      {/* Header */}
      <div className="p-6 border-b border-stone-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-ink-500 font-display">{title}</h2>
            {badge && (
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-stone-100 text-stone-600">
                {badge}
              </span>
            )}
          </div>
          {description && <p className="text-stone-500 text-sm mt-1">{description}</p>}
        </div>

        {isDirty && (
          <div className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full font-medium self-start sm:self-auto">
            <AlertCircle size={13} />
            <span>Unsaved changes</span>
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="px-6 py-3 bg-red-50 border-b border-red-100 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Form Content */}
      <div className="p-6">{children}</div>

      {/* Action Footer (only if actions provided) */}
      {(onSave || onReset) && (
        <div className="px-6 py-4 bg-stone-50/75 border-t border-stone-100 flex flex-col-reverse sm:flex-row items-center justify-between gap-3">
          <div>
            {onReset && (
              <Button
                type="button"
                variant="secondary"
                disabled={loading}
                onClick={handleResetClick}
                className="text-stone-600 hover:text-stone-900 w-full sm:w-auto text-xs"
              >
                <RotateCcw size={14} className="mr-1.5" />
                {resetConfirming ? "Confirm Reset to Defaults?" : "Reset to Defaults"}
              </Button>
            )}
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            {onSave && (
              <Button
                type="button"
                variant="primary"
                loading={loading}
                disabled={!isDirty || loading}
                onClick={onSave}
                className="w-full sm:w-auto"
              >
                <Save size={15} className="mr-1.5" />
                Save Changes
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
