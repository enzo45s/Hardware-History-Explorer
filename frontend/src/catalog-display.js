// Display aliases never replace the stored keys used by imports and evidence.
export function displaySpecification(spec) {
  return { ...(spec.normalized || spec), ...spec.display };
}

export const displayDescription = item => item.display_description ?? item.description;
export const displayConfigurationName = config => config.display_name ?? config.variant_name;
