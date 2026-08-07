declare module 'markdown-it-texmath' {
  import type MarkdownIt from 'markdown-it';
  import type { KatexOptions } from 'katex';

  type TexMathDelimiter =
    | 'dollars'
    | 'brackets'
    | 'doxygen'
    | 'gitlab'
    | 'julia'
    | 'kramdown'
    | 'beg_end';

  interface TexMathOptions {
    engine: {
      renderToString(expression: string, options?: KatexOptions): string;
    };
    delimiters?: TexMathDelimiter | TexMathDelimiter[];
    katexOptions?: KatexOptions;
    outerSpace?: boolean;
  }

  const texmath: (md: MarkdownIt, options: TexMathOptions) => void;
  export default texmath;
}
