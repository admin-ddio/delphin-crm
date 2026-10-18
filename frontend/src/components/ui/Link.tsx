/**
 * PROVISIONAL. Replace with a verbatim port of the pilot's link primitive.
 * Framework swap only: next/link -> React Router Link. The pilot disables
 * prefetch; React Router's default (`prefetch` unset = none) matches that.
 */
import { forwardRef } from 'react';
import { Link as RouterLink, type LinkProps as RouterLinkProps } from 'react-router';

export type LinkProps = Omit<RouterLinkProps, 'prefetch'>;

export const Link = forwardRef<HTMLAnchorElement, LinkProps>(function Link(props, ref) {
  return <RouterLink ref={ref} {...props} />;
});
