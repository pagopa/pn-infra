# Minimum adequate solution

Before designing, establish the behavior that needs to change and inspect the relevant existing implementation and SEND references.

Consider whether configuration alone satisfies the request, whether an existing fragment or module already covers it, and whether a local change preserves the established contracts. Introduce a new abstraction or resource only when the existing options fail a concrete requirement.

For a substantial new component, compare a feature-specific implementation with a reusable building block when another concrete use shares the same responsibility. Check the proposed interface and whether sharing would couple permissions, deployment, or operations; do not generalize for hypothetical future users. See [Evaluate components as building blocks](../references/iac-guidelines.md#evaluate-components-as-building-blocks) for the detailed rule.

Choose the smallest coherent solution that meets security, reliability, observability and maintainability needs. Fewer files or lines are not sufficient evidence of a better solution. Do not remove necessary alarms, permissions boundaries or compatibility handling to simplify a diff.

For a material design choice, explain the recommended approach and the relevant alternative in a few sentences. For a clear local edit, perform this assessment without producing a separate checklist or document. Do not redesign unrelated infrastructure.
