// TypeScript global type augmentations for Vue templates
// Augment EventTarget to include common input element properties
declare global {
    interface EventTarget {
        value?: any;  // Use any to avoid type conflicts
        checked?: any;
    }
}

export { };
