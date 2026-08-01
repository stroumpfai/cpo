import { useEffect, useState } from 'react';
import { api } from '../api.js';

/**
 * Discreet build-version label, shared by the CPO sidebar and the admin header.
 *
 * Renders a bare <span> with no margins of its own so each host controls
 * placement. Renders nothing at all if the request fails — a missing version
 * label should never be more visible than the version itself.
 */
export function VersionLabel() {
  const [build, setBuild] = useState(null);

  useEffect(() => {
    api.get('/version').then(setBuild).catch(() => {});
  }, []);

  if (!build?.version) return null;

  // "unknown" is the Dockerfile's default when a build is not stamped with a
  // commit — no point offering it as a tooltip.
  const commit = build.commit && build.commit !== 'unknown' ? build.commit : null;

  return (
    <span
      className="text-xs text-faint"
      title={commit ? `commit ${commit}` : undefined}
    >
      v{build.version}
    </span>
  );
}
