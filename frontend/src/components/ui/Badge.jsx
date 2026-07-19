import clsx from "clsx";

const variants = {
  green : "badge-green",
  blue  : "badge-blue",
  yellow: "badge-yellow",
  red   : "badge-red",
  purple: "badge-purple",
  gray  : "badge bg-dark-700 text-dark-300 border border-dark-600"
};

const statusMap = {
  screened   : "blue",
  shortlisted: "green",
  invited    : "purple",
  hired      : "green",
  rejected   : "red",
  active     : "green",
  closed     : "gray",
  advance    : "green",
  reject     : "red"
};

export default function Badge({ children, variant, status }) {
  const v = variant || statusMap[status] || "gray";
  return (
    <span className={clsx(variants[v])}>
      {children}
    </span>
  );
}