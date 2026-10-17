<script lang="ts" module>
  import { tv, type VariantProps } from "tailwind-variants";

  export const button = tv({
    base: "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-ctl text-[13px] font-medium transition-colors select-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
    variants: {
      variant: {
        primary: "bg-accent text-accent-ink hover:opacity-90",
        secondary: "border border-line bg-surface text-ink hover:bg-hover",
        ghost: "text-ink-2 hover:bg-hover hover:text-ink",
        danger: "bg-bad text-white hover:opacity-90",
        link: "h-auto px-0 text-accent underline-offset-4 hover:underline",
      },
      size: { sm: "h-7 px-2.5", md: "h-8 px-3", lg: "h-9 px-4 text-sm", icon: "size-8", "icon-sm": "size-7 [&_svg]:size-[15px]" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  });
  export type ButtonProps = VariantProps<typeof button>;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLButtonAttributes } from "svelte/elements";

  let { variant, size, class: cls = "", children, ref = $bindable(null), ...rest }: Omit<HTMLButtonAttributes, "class"> & ButtonProps & { class?: string; children?: Snippet; ref?: HTMLButtonElement | null } = $props();
</script>

<button bind:this={ref} type="button" class={button({ variant, size, class: cls })} {...rest}>{@render children?.()}</button>
