// This is a Mako (http://docs.makotemplates.org/) template of a C-source code (C99) file

<%!
from pycompilation.codeexport import Loop 
%>


<%def name="render_group(group)">
%for line in group:
    ${line.lhs} = ${line.rhs};
%endfor
</%def>


<%def name="nested_loop(counter, bounds_idx, body, type='int')">
  for (${type} ${counter}=bounds[bounds_idx*2]; ${counter} < bounds[bounds_idx*2+1]; ++${counter}){ 
    ${loop(*body) if isinstance(body, Loop) else render_group(body)}
  } 
</%def>


void func(const int * const restrict bounds,
	  const double * const restrict input,
	  double * restrict output)
{
  %for group in expr_groups:
  ${nested_loop(*group) if isinstance(group, Loop) else render_group(group)}
  %endfor
}
