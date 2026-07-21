import clsx from "clsx";

const variants = {
  green : "badge-green",
  blue  : "badge-blue",
  yellow: "badge-yellow",
  red   : "badge-red",
  purple: "badge-purple",
  gray  : "badge-gray"
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
  reject     : "red",
  pending    : "yellow"
};

export default function Badge({ children, variant, status, className }) {
  const v = variant || statusMap[status] || "gray";
  return (
    <span className={clsx(variants[v], className)}>
      {children}
    </span>
  );
}