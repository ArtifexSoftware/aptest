#! /usr/bin/env python3

import sys
import time

import backtrace
import dictpath
import json
import pipcl


# Get improved display of exceptions and stacktraces.
backtrace.exception_hook_install()

def _sorted_items( d):
    '''
    Like dict.items() but uses sorted keys.
    '''
    keys = list( d.keys())
    keys.sort()
    for key in keys:
        value = d[ key]
        yield key, value


def plotly_figure(data, graph_height=400):
    '''
    Returns a plotly.graph_objects.Figure.
    
    Args:
        data: A structured dict:
            {
                graphname:
                {
                    'xaxis_name': str|None,
                    'yaxis_name': str,
                    'lines':
                    {
                        line_name: str,
                        {
                            'points':
                            [
                                (x, y),
                                ...
                            ],
                        },
                    },
                },
            }
    '''
    import plotly.subplots
    import plotly.graph_objects
    import numpy
    
    # Define a color for each tool.
    #
    # We use hard-coded strong colors for pymupdf tools, then
    # plotly.colors.DEFAULT_PLOTLY_COLORS for the rest.
    #
    if 0:
        palette = [
                'rgb(255, 0, 0)',
                'rgb(0, 0, 255)',
                'rgb(128, 0, 128)',
                ] + list(plotly.colors.DEFAULT_PLOTLY_COLORS)
        tool_colors = dict()
        def tool_order(tool):
            if tool != 'pymupdf' and (tool.startswith('pymupdf') or tool.startswith('mupdfpy')):
                return 'aaaaa' + tool
            return tool
        for i, tool in enumerate( sorted(tools, key=tool_order)):
            tool_colors[ tool] = palette[ i % len(palette)]
            #jlib.log('{tool}: {tool_colors[ tool]}')
    
    palette = list(plotly.colors.DEFAULT_PLOTLY_COLORS)
    
    # We need to find, in advance, the number of subplots and the subplot
    # titles (e.g. 'copy: DB-Systems.pdf').
    #
    num_subplots = len(data)
    subplot_titles = list()
    for graphname, lines in _sorted_items(data):
        subplot_titles.append(graphname)
    
    # Create the subplots.
    #
    height = graph_height * num_subplots
    vertical_spacing_max = 1 / num_subplots
    vertical_spacing = vertical_spacing_max * 0.2
    figure = plotly.subplots.make_subplots(
            rows=num_subplots,
            cols=1,
            vertical_spacing=vertical_spacing,
            subplot_titles=subplot_titles,
            #print_grid=True,   # print ids for each suplot.
            )
    
    annotations = list()
    
    # Add plots for each line to each subplot.
    #
    
    for i, (graphname, graph) in enumerate(_sorted_items(data)):
        pipcl.log(f'{i=} {graphname=}')
        if graph['xaxis_name'] is None:
            figure.update_xaxes(title_text='Date/time', row=1+i, col=1)
        else:
            figure.update_xaxes(title_text=graph['xaxis_name'], row=1+i, col=1)
        figure.update_yaxes(title_text=graph['yaxis_name'], row=1+i, col=1)
        
        rhs = list()
        
        for linename, line in _sorted_items(graph['lines']):
            pipcl.log(f'{linename=} {line=}')
                
            # Find points for this line.
            xs = []
            ys = []
            for x, y in sorted(line['points']):
                date = numpy.datetime64(int(x*1000), 'ms')
                xs.append( date)
                ys.append( y)

            assert len(xs) == len(ys)
            # Add trace for this line.
            figure.add_trace(
                    plotly.graph_objects.Scatter(
                        x = xs,
                        y = ys,
                        #marker=dict(color=line_colors[line], size=10, symbol='x',
                        #        maxdisplayed=0),
                        mode = 'lines+markers',
                        ),
                    row = 1+i,
                    col = 1,
                    )

            # Update `rhs` with location of final point.
            if xs and ys:
                x, y = xs[-1], ys[-1]
                x0 = xs[0]
                rhs.append( (x, y, linename))
            
            # Create dummy transparent trace with y=0 so that y axis always
            # includes zero.
            #
            if 0 and rhs:
                # Use any existing x coordinate.
                x, _, _ = rhs[0]
                figure.add_trace(
                        plotly.graph_objects.Scatter(
                            x = [x],
                            y = [0],
                            marker=dict(opacity=[0]),
                            ),
                        row = 1+i,
                        col = 1,
                        )
            
        pipcl.log(f'rhs:')
        for rhs_item in rhs:
            pipcl.log(f'    {rhs_item}')
        # Add specifications for annotations on the right hand side of each
        # of this subplot's lines.
        #
        # We need to do this in order of y coordinate, so that we can add
        # an increasing pixel-based y offset so that the annotations do not
        # overlap each other.
        #
                
        rhs.sort( key=lambda item: item[1])
        for j, (x, y, linename) in enumerate(rhs):
            pixel_offset_x = 60
            pixel_offset_y = - (j+0.5 - len(rhs)/2) * 12    # Default font is 12 pixels hight?
            pipcl.log(f'Adding annotation: {x=} {y=} {linename=}')
            annotations.append(
                    dict(
                        # Identify subplot axes.
                        xref=f'x{1+i if i else ""}',
                        yref=f'y{1+i if i else ""}',

                        # Where the annotation arrow points to.
                        x=x,
                        y=y,

                        text=f'{y:.2f} {linename}',

                        # Place annotation text at pixel offset from (x, y).
                        axref='pixel',
                        ayref='pixel',
                        ax=pixel_offset_x,
                        ay=pixel_offset_y,

                        # Specify arrow head near to (x, y).
                        showarrow=True,
                        arrowhead=3,    # Shape of arrow head.
                        arrowsize=1,
                        standoff=4, # arrow head distance from (x, y) in pixels.

                        # startarrow* seems to have no effect?
                        #startarrowhead=2,
                        #startarrowsize=3,

                        xanchor='left', # Make tail of arrow be at left of annotation text.

                        # Set annotation color to color of the line.
                        #font=dict(color=tool_colors[tool])
                        )
                    )
    
    # fixme: doubling the list of annotations seems to fix issue where if there
    # are a large numbers of annotations, the first few seem to be omitted.
    #
    annotations += annotations
    
    figure.update_layout(
            annotations=annotations,
            autosize=True,
            margin=dict(
                autoexpand=True,
                ),
            height=height,
            showlegend=False,
            )
    
    return figure


def plotly_html(data, path_out):
    '''
    Creates html file containing interactive graph(s) generated from data.

    data:
        See plotly_figure().

    path_out:
        Output html path.
    '''
    
    figure = plotly_figure(data, graph_height=600)
    
    # Save `figure` to a .html file containing interactive graphs.
    figure.write_html(
            path_out,
            # See: https://github.com/plotly/plotly.js/blob/master/src/plot_api/plot_config.js
            config=dict(
                scrollZoom=True,
                #doubleClick='reset',
                showTips=True,
                )
            )

def plot_gnn_html(paths, out_html):
    '''
    Generates an .html file containing graphs showing one or more gnn test
    runs.
    
    Args:
        data:
            List of .json file paths from aptest/aptest.py's
            `test-gnn-pymupdf4llm` command.
        out_html:
            Output file.
    '''
    inputdata = dict()
    for path in paths:
        with open(path) as f:
            d = json.load(f)
            inputdata[path] = d
    
    # Create graphs showing scores.
    data = dict()
    graphs = dict()
    dictpath.setpath(graphs, '__overall__', ['precision', 'recall', 'f1'])
    for graphname, lines in _sorted_items(graphs):
        dictpath.setpath(data, graphname, 'xaxis_name', None)
        dictpath.setpath(data, graphname, 'yaxis_name', 'Score')
    # Populate <data>.
    for path, d in inputdata.items():
        for graphname, linenames in _sorted_items(graphs):
            for linename in linenames:
                if graphname not in d['results']:
                    continue
                value = d['results'][graphname].get(linename)
                if value is not None:
                    t = d['t_start']
                    point = (t, value)
                    dictpath.setpathdefault(data, graphname, 'lines', linename, 'points', list()).append(point)

    # Create graph showing t_duration.
    graphname = 'duration'
    for path, d in _sorted_items(inputdata):
        dictpath.setpath(data, graphname, 'xaxis_name', None)
        dictpath.setpath(data, graphname, 'yaxis_name', 'Time')
        t = d['t_start']
        duration = d['t_duration']
        point = (t, duration)
        dictpath.setpathdefault(data, graphname, 'lines', 'duration', 'points', list()).append(point)

    pipcl.log(f'data:\n{json.dumps(data, indent="    ", sort_keys=1)}')
    plotly_html(data, out_html)


def plot_gnn_html_select(
        out_html,
        filterfn=lambda results: True,
        ppr=None,
        ppr_git_branch='main',
        ppr_git_text=None,
        ):
    '''
    Gemerates graphs for gnn results for which <filterfn()> returns true.
    
    Args:
        out_html:
            Output path.
        filterfn:
            Should return true if supplied <results> dict matches.
        ppr:
            Specification of PyMuPDF-performance-results checkout. See
            pipcl.py:git_get()'s <text> arg.
    
    Example usage:
        def fn(results):
            if results['python']['platform.system()'] != 'Windows':
                return
            if results['state']['limit']:
                return
            return True
        graph.plot_gnn_html_select(
                'gnn-graph.html',
                filterfn = fn,
                ppr = 'git:-b jules',
                )
        firefox gnn-graph.html
    '''
    ppr_path = pipcl.git_get(
            'aptest-git-pymupdf-performance-results',
            remote='git@github.com:ArtifexSoftware/PyMuPDF-performance-results.git',
            branch=ppr_git_branch,
            text=ppr,
            )
    paths = list()
    for path in glob.glob(f'{ppr_path}/test-gnn-pymupdf4llm-*.json'):
        with open(path) as f:
            results = json.load(f)
        if filterfn(results):
            paths.append(path)
    plot_gnn_html(paths, out_html)
    

if __name__ == '__main__':
    args = iter(sys.argv[1:])
    while 1:
        try:
            arg = next(args)
        except StopIteration:
            break
        if arg == 'test':
            pipcl.run(f'pip install numpy plotly')
            t0 = int(time.time())
            data = {
                    'graph 1':
                    {
                        'xaxis_name': None,
                        'yaxis_name': 'y values',
                        'lines':
                        {
                            'foo':
                            {
                                'points':
                                #'y values':
                                [
                                    (t0 + 9.1, 1),
                                    (t0 + 2, 3),
                                    (t0 + 3, 2),
                                    (t0 + 4, 1),
                                    (t0 + 5, 2),
                                    (t0 + 6, 3),
                                ],
                            },
                            'bar':
                            {
                                'points':
                                [
                                    (t0 + 1, 2),
                                    (t0 + 2, 2),
                                    (t0 + 3, 1),
                                    (t0 + 4, 2),
                                    (t0 + 5, 3),
                                    (t0 + 6, 5),
                                ],
                            },
                        },
                    },
                    }
            plotly_html(data, 'aptest_test_graph.html')
        
        elif arg == '-i':
            pipcl.run(f'pip install numpy plotly')
            inputdata = dict()
            paths = [path for path in args]
            plot_gnn_html(paths, 'aptest_test_graph.html')
            
        else:
            assert 0, f'Unrecognised {arg=}.'
