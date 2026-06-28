# Jekyll integration

Copy `_includes/paper-radar.liquid` into the target Jekyll site's `_includes`
directory. Then place this in any Markdown or Liquid page:

```liquid
{% include paper-radar.liquid
   base_url="https://hwyii.github.io/dawnlit"
   limit=3
   heading="Recent papers"
   description="Selected around my current research interests."
%}
```

The component uses Shadow DOM, so the host site's theme should not override its
card styles. Set `theme="light"`, `theme="dark"`, or leave the default `auto`.

The hosted `papers.json` response must permit cross-origin reads when the widget
and host site use different domains. GitHub Pages files are generally readable
cross-origin; a custom API should return an appropriate
`Access-Control-Allow-Origin` header.
