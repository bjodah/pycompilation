// This is a Mako (http://docs.makotemplates.org/) template of a C-source code (C99) file

##// Essentially "import pycompilation.codeexport as ce"
<%namespace name="ce" module="pycompilation.codeexport"/>


<%def name="render_group(group)">
%for line in group:
    ${line.lhs} = ${line.rhs};
%endfor
</%def>


<%def name="nested_loop(counter, bounds_idx, body, type='int')">
  for (${type} ${counter}=bounds[bounds_idx*2]; ${counter} < bounds[bounds_idx*2+1]; ++${counter}){ 
    ${loop(*body) if isinstance(body, ce.Loop) else render_group(body)}
  } 
</%def>

// func takes arbitrary (<~ 2e9) number of ints and doubles as input (inpd/inpi)
// and populates arbitrary number of ints and doubles in outd/outi
// returns 0 on successful exit;
int _arbitrary_func(const int * const restrict bounds,
		    const double * const restrict inpd,
		    const int * const restrict inpi,
		    const double * restrict outd,
		    const double * restrict outi)
{
  %for group in expr_groups:
  ${nested_loop(*group) if isinstance(group, ce.Loop) else render_group(group)}
  %endfor
  return 0;
}
