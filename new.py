import os
import cv2
import copy
import datetime
import numpy as np
import random as rd
import operator as op
import functools as ft
import itertools as it
import collections as col

from skan import csr
from os import listdir
from skimage import morphology
from os.path import isfile, join
from decimal import Decimal, getcontext

# from concurrent.futures import ProcessPoolExecutor
# from concurrent import futures


# ---------------------------------------------------------------------------------
# draw_edges(edges, edge_dictionary, image, color):
def draw_edges(edges, edge_dictionary, image, color):
    for edge in edges:
        edge_list = edge_dictionary[edge]
        image = overlay_edges(image, edge_list, color)
    return image


def overlay_edges(image, edge_list, color=None):
    image_copy = copy.deepcopy(image)

    # random_color = (100, 156, 88)
    if color is None:
        random_color = (rd.randint(50, 255), rd.randint(50, 255), rd.randint(50, 255))
    else:
        random_color = color
    for point in edge_list:
        # print('point=', point)
        # cv2.circle(image, point, radius, random_color, cv2.FILLED)
        r, g, b = image_copy[point]
        if r == 0 and g == 0 and b == 0:
            image_copy[point] = random_color
        else:
            image_copy[point] = (255, 255, 255)
    return image_copy


# ---------------------------------------------------------------------------------
# draw_graph_edges
def draw_graph_edges(edge_dictionary, ridges_mask, window_name, wait_flag=False):
    after_ridge_mask = cv2.cvtColor(np.zeros_like(ridges_mask), cv2.COLOR_GRAY2RGB)
    for edge_list in edge_dictionary.values():
        colors = []
        random_color = (rd.randint(50, 200), rd.randint(50, 200), rd.randint(50, 200))
        while random_color in colors:
            random_color = (rd.randint(50, 200), rd.randint(50, 200), rd.randint(50, 200))
        after_ridge_mask = overlay_edges(after_ridge_mask, edge_list, random_color)
        colors.append(random_color)
    for two_vertex in edge_dictionary.keys():
        v1, v2 = two_vertex
        after_ridge_mask[v1] = (255, 255, 255)
        after_ridge_mask[v2] = (255, 255, 255)

    # cv2.namedWindow(window_name)
    # cv2.imshow(window_name, after_ridge_mask)
    # cv2.imwrite(window_name + '.png', after_ridge_mask)
    if wait_flag:
        cv2.waitKey()
        cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------
# document pre processing
def pre_process(path):
    # load image as gray-scale,
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    # convert to binary using otsu binarization
    image = cv2.threshold(image, 0, 1, cv2.THRESH_OTSU)[1]
    # add white border around image of size 29
    white_border_added = cv2.copyMakeBorder(image, 29, 29, 29, 29, cv2.BORDER_CONSTANT, None, 1)
    # on top of that add black border of size 1
    black_border_added = cv2.copyMakeBorder(white_border_added, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, 0)
    # cv2.imwrite('black_border_added.png', black_border_added*255)
    return black_border_added


# ---------------------------------------------------------------------------------
# returns for edge (u,v) its shortest connected list of pixels from pixel u to pixel v
def edge_bfs(start, end, skeleton):

    visited = set()
    to_visit = col.deque([start])
    edges = col.deque()
    done = False
    while not done and to_visit:
        current = to_visit.popleft()
        visited.add(current)
        candidates = [v for v in connected_candidates(current, skeleton)
                      if v not in visited and v not in to_visit]
        # print('candidates=', candidates)
        for vertex in candidates:
            edges.append([current, vertex])
            to_visit.append(vertex)
            if vertex == end:
                done = True
    # print('start=', start, 'end=', end)
    # print('candidates=', edges)
    # exit()

    # find path from end -> start
    final_edges = [end]
    current = end
    failed = False
    while current != start and not failed:
        # print('current=', current)
        sub_edges = list(filter(lambda item: item[1] == current, edges))
        # print('sub_edges=', sub_edges)
        if sub_edges:
            one_edge = sub_edges.pop()
            final_edges.append(one_edge[0])
            current = one_edge[0]
        else:
            failed = True

    final_edges.append(start)
    # print('finalEdges=', final_edges)
    # exit()

    if failed:
        print(start, end, 'fail')
        return start, end, []
    else:
        # print(start, end, 'success')
        return start, end, final_edges


# ---------------------------------------------------------------------------------
# retrieves connected pixels that are part of the edge pixels
# to be used for the bfs algorithm
# 8 connected neighborhood of a pixel
def connected_candidates(pixel, skeleton):
    def add_offset(offset):
        return tuple(map(op.add, pixel, offset))

    def in_bounds_and_true(p):
        r, c = add_offset(p)
        if 0 <= r < skeleton.shape[0] and 0 <= c <= skeleton.shape[1] and skeleton[r][c]:
            return True
        else:
            return False

    eight_connected = list(filter(in_bounds_and_true, [(1, 0), (0, 1), (-1, 0), (0, -1),
                                                                      (1, 1), (-1, 1), (-1, -1), (1, -1)]))

    return [add_offset(offset) for offset in eight_connected]


# ---------------------------------------------------------------------------------
# extract local maxima pixels
def calculate_local_maxima_mask(image):
    def uint8_array(rows):
        return np.array(rows).astype(np.uint8)

    base = list(map(uint8_array, [
        [
            [0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0],
        ],
        [
            [0, 1, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0],
        ],
        [
            [0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0],
        ],
    ]))

    kernels = [mat for mat in base + [mat.T for mat in base]]

    local_maxima_result = (image > cv2.dilate(image, kernel)
                           for kernel in kernels)

    return ft.reduce(op.or_, local_maxima_result).astype(np.uint8)


def time_print(msg):
    print('[' + str(datetime.datetime.now()) + ']', msg)


# -
# All vertexes with one degree (take part of one edge only) - they are removed
# All vertexes with two degree (take part of two edges exactly) - they are merged
# this is done iteratively, until all vertexes have a degree of three or more!
def remove_one_degree_edges(skeleton, iter_index, file_name):
    def identical(e1, e2):
        return e1[0] == e2[0] and e1[1] == e2[1]

    cv2.imwrite('./' + file_name + '/skel_' + str(iter_index) + '.png', skeleton.astype(np.uint8) * 255)
    # important! removes pixels due to vertex removal from previous iteration
    skeleton = morphology.skeletonize(skeleton)
    # TODO add to paper information about this !!! remove redundant edges
    # summarization shows each edge, its start and end pixel, length, distance, etc
    # ALSO!! it has two types of edges, one that has two vertexes in graph
    # others that have one vertex only - those to be removed!
    # TODO THESE ARE EDGE END POINTS - TWO VERTEX COORDINATES FOR EACH EDGE
    branch_data = csr.summarise(skeleton)
    coords_cols = (['img-coord-0-%i' % i for i in [1, 0]] +
                   ['img-coord-1-%i' % i for i in [1, 0]])
    coords = branch_data[coords_cols].values.reshape((-1, 2, 2))
    # TODO Each Vertex to stay in the graph needs to have a degree of two or more
    # TODO Iteratively, we remove those that have less than two degree
    # TODO We stop only when there are no more vertexes left with low degree
    # TODO THEN WE EXTRACT THE EDGES - USING BFS ?! NEED TO FIND A GOOD WAY

    try_again = False
    len_before = len(coords)
    done = False
    while not done:
        changed = False
        flat_coords = [tuple(val) for sublist in coords for val in sublist]
        unique_flat_coords = list(set(flat_coords))
        current = 0
        while not changed and current < len(unique_flat_coords):
            item = unique_flat_coords[current]
            current += 1
            # print('item=', item, 'count=', flat_coords.count(item))
            # 1 degree vertexes are to be removed from graph
            if flat_coords.count(item) < 2:
                changed = True
                fc = list(filter(lambda x: tuple(x[0]) == item or tuple(x[1]) == item, coords))
                coords = list(filter(lambda x: tuple(x[0]) != item and tuple(x[1]) != item, coords))
                # print('flat_coords.count(item)=', flat_coords.count(item), 'fc=', fc)
            # 2 degree vertexes need their edges to be merged
            elif flat_coords.count(item) == 2:
                changed = True
                fc = list(filter(lambda x: tuple(x[0]) == item or tuple(x[1]) == item, coords))
                # print('flat_coords.count(item)=', flat_coords.count(item), 'fc=', fc)
                if len(fc) != 2:
                    print('item=', item, 'fc=', fc)
                coords = list(filter(lambda x: tuple(x[0]) != item and tuple(x[1]) != item, coords))
                e1_s = fc[0][0]
                e1_e = fc[0][1]
                e2_s = fc[1][0]
                e2_e = fc[1][1]
                if ft.reduce(op.and_, map(lambda e: e[0] == e[1], zip(e1_s, e2_s))) and \
                        not identical(e1_e, e2_e):
                    coords.append(np.array([e1_e, e2_e]))
                elif ft.reduce(op.and_, map(lambda e: e[0] == e[1], zip(e1_s, e2_e))) and \
                        not identical(e1_e, e2_s):
                    coords.append(np.array([e1_e, e2_s]))
                elif ft.reduce(op.and_, map(lambda e: e[0] == e[1], zip(e1_e, e2_s))) and \
                        not identical(e1_s, e2_e):
                    coords.append(np.array([e1_s, e2_e]))
                elif ft.reduce(op.and_, map(lambda e: e[0] == e[1], zip(e1_e, e2_e))) and \
                        not identical(e1_s, e2_s):
                    coords.append(np.array([e1_s, e2_s]))
                else:
                    changed = False
        if not changed:
            done = True
            time_print('before= ' + str(len_before) + ' after= ' + str(len(coords)))
            try_again = len_before != len(coords)

    skel = cv2.cvtColor(skeleton.astype(np.uint8) * 255, cv2.COLOR_GRAY2RGB)
    # cv2.namedWindow('skeleton')
    # cv2.imwrite('skeleton.png', skel)
    # cv2.imshow('skeleton', skel)
    # TODO DISCONNECT EVERY JUNCTION - THIS HELPS BFS CONVERGE FASTER!
    tmp_skel = copy.deepcopy(skeleton)
    for coord in coords:
        start, end = coord
        start = (start[1], start[0])
        end = (end[1], end[0])
        # print(start, end)
        start_neighborhood = connected_candidates(start, skeleton)
        end_neighborhood = connected_candidates(end, skeleton)
        for point in start_neighborhood + end_neighborhood:
            tmp_skel[point] = False
        tmp_skel[start] = False
        tmp_skel[end] = False
    # cv2.namedWindow('skeleton_junctions')
    # cv2.imwrite('skeleton_junctions.png', skel)
    # cv2.imshow('skeleton_junctions', skel)

    # TODO NOW WE EXTRACT EDGES, FIND BFS (SHORTEST PATH) BETWEEN TWO GIVEN VERTEXES
    cv2.imwrite('./' + file_name + '/base_' + str(iter_index) + '.png', tmp_skel.astype(np.uint8) * 255)

    skel = np.zeros_like(skeleton)
    results = []
    for edge in coords:
        start, end = edge
        start = (start[1], start[0])
        end = (end[1], end[0])
        start_neighborhood = connected_candidates(start, skeleton)
        end_neighborhood = connected_candidates(end, skeleton)
        for point in start_neighborhood + end_neighborhood:
            tmp_skel[point] = True
        tmp_skel[start] = True
        tmp_skel[end] = True
        _, _, result = edge_bfs(start, end, tmp_skel)
        start_neighborhood = connected_candidates(start, skeleton)
        end_neighborhood = connected_candidates(end, skeleton)
        for point in start_neighborhood + end_neighborhood:
             tmp_skel[point] = False
        tmp_skel[start] = False
        tmp_skel[end] = False
        results.append((start, end, result))
        for point in result:
            skel[point] = True

    colors = []
    image = cv2.cvtColor(np.zeros_like(skeleton, np.uint8), cv2.COLOR_GRAY2RGB)
    for result in results:
        start, end, edge_list = result
        random_color = (rd.randint(50, 200), rd.randint(50, 200), rd.randint(50, 200))
        while random_color in colors:
            random_color = (rd.randint(50, 200), rd.randint(50, 200), rd.randint(50, 200))
        for point in edge_list:
            image[point] = random_color
        colors.append(random_color)
    cv2.imwrite('./' + file_name + '/iter_' + str(iter_index) + '.png', image)
    return skel, results, try_again


# ---------------------------------------------------------------------------------
# ridge extraction
def ridge_extraction(image_preprocessed, file_name):
    # apply distance transform then normalize image for viewing
    dist_transform = cv2.distanceTransform(image_preprocessed, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    # normalize distance transform to be of values [0,1]
    normalized_dist_transform = cv2.normalize(dist_transform, None, 0, 1.0, cv2.NORM_MINMAX)
    # extract local maxima pixels -- "ridge pixels"
    dist_maxima_mask = calculate_local_maxima_mask(normalized_dist_transform)
    # retrieve the biggest connected component only
    dist_maxima_mask_biggest_component = np.zeros_like(dist_maxima_mask)

    for val in np.unique(dist_maxima_mask)[1:]:
        mask = np.uint8(dist_maxima_mask == val)
        labels, stats = cv2.connectedComponentsWithStats(mask, 4)[1:3]
        largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        dist_maxima_mask_biggest_component[labels == largest_label] = val
    # extract local maxima pixels magnitude values from the distance transform
    dist_maxima = np.multiply(dist_maxima_mask_biggest_component, dist_transform)
    # TODO show before and after result
    # cv2.namedWindow('before')
    # cv2.imshow('before', dist_maxima_mask_biggest_component * 255)
    # cv2.imwrite('before_zhang.png', dist_maxima_mask_biggest_component * 255)
    # TODO check which skeletonization is used !!!!! The skeleton is thinned usign this method
    # we extract our own skeleton, here we just use thinning after ridge extraction
    skeleton = morphology.skeletonize(dist_maxima_mask_biggest_component)
    # TODO THIS SKELETONIZATION USES -> [Zha84]	(1, 2) A fast parallel algorithm for thinning digital patterns, T. Y. Zhang and C. Y. Suen, Communications of the ACM, March 1984, Volume 27, Number 3.
    # cv2.imwrite('skeleton.png', dist_maxima_mask_biggest_component.astype(np.uint8) * 255)
    # TODO to add to paper!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # degree has each pixel and # of neighbors, to distinguish junction from non junction
    # so far I think 3+ neighbors are chosen, but begin from highest number of neighbors in greedy manner
    # each time if a pixel chosen as junction, a nearby pixel cannot be chosen as junction even if it fits
    # the minimum number of pixels

    # cv2.imwrite('degrees.png', cv2.normalize(degrees, None, 0, 255, cv2.NORM_MINMAX))
    # TODO add to paper information about this !!! remove redundant edges
    # summarization shows each edge, its start and end pixel, length, distance, etc
    # ALSO!! it has two types of edges, one that has two vertexes in graph
    # others that have one vertex only - those to be removed!
    # TODO THESE ARE EDGE END POINTS - TWO VERTEX COORDINATES FOR EACH EDGE
    # branch_data, g, coords_img, skeleton_ids, num_skeletons = csr.summarise(skeleton)
    # coords_cols = (['img-coord-0-%i' % i for i in [1, 0]] +
    #                ['img-coord-1-%i' % i for i in [1, 0]])
    # coords = branch_data[coords_cols].values.reshape((-1, 2, 2))
    # TODO Each Vertex to stay in the graph needs to have a degree of two or more
    # TODO Iteratively, we remove those that have less than two degree
    # TODO We stop only when there are no more vertexes left with low degree
    # TODO THEN WE EXTRACT THE EDGES - USING BFS ?! NEED TO FIND A GOOD WAY

    changed = True
    results = []
    iter_index = 0
    while changed:
        time_print('iter ' + str(iter_index))
        skeleton, results, changed = remove_one_degree_edges(skeleton, iter_index, file_name)
        iter_index += 1
    time_print('done')
    colors = []
    image = cv2.cvtColor(np.zeros_like(skeleton, np.uint8), cv2.COLOR_GRAY2RGB)
    edge_dictionary = dict()
    for result in results:
        start, end, edge_list = result
        if start == end:  # TODO WHY THE GRAPH HAS THESE EDGES? BUG IN LIBRARY?
            continue
        edge_dictionary[(start, end)] = edge_list
        random_color = (rd.randint(50, 200), rd.randint(50, 200), rd.randint(50, 200))
        while random_color in colors:
            random_color = (rd.randint(50, 200), rd.randint(50, 200), rd.randint(50, 200))
        for point in edge_list:
            image[point] = random_color
        colors.append(random_color)
    cv2.imwrite('./' + file_name + '/edges.png', image)
    # cv2.namedWindow('resultFinal')
    # cv2.imshow('resultFinal', image)
    # cv2.waitKey()
    # cv2.destroyAllWindows()
    return skeleton, edge_dictionary


# ---------------------------------------------------------------------------------
# calculates angle between three points, result in radians
# using Decimal for increased precision
def calculate_abs_angle(u, v, w):
    # angle between u, v and v, w
    getcontext().prec = 28

    u_x, u_y = u
    v_x, v_y = v
    w_x, w_y = w

    x1 = (u_x - v_x).item()
    y1 = (u_y - v_y).item()
    x2 = (w_x - v_x).item()
    y2 = (w_y - v_y).item()

    dot = Decimal(x1 * x2 + y1 * y2)
    norma_1 = Decimal(x1 * x1 + y1 * y1).sqrt()
    norma_2 = Decimal(x2 * x2 + y2 * y2).sqrt()
    if norma_1 == 0.0:
        print('norma_1==0->', u, v, w)
        norma_1 = Decimal(0.0001)
    if norma_2 == 0.0:
        print('norma_2==0->', u, v, w)
        norma_2 = Decimal(0.0001)
    val = dot / (norma_1 * norma_2)

    return np.abs(np.arccos(float(val)))


# ---------------------------------------------------------------------------------
# get_nearby_pixels
def get_nearby_pixels(u, v, w1, w2, edges_dictionary, max_dist):
    v_x, v_y = v
    max_dist_v = [x for x in range(-max_dist, max_dist + 1)]
    max_dist_candidates_x = list(map(lambda x: x + v_x, max_dist_v))
    max_dist_candidates_y = list(map(lambda y: y + v_y, max_dist_v))

    left_column = list(map(lambda e: (v_x - max_dist, e), max_dist_candidates_y))
    right_column = list(map(lambda e: (v_x + max_dist, e), max_dist_candidates_y))
    top_column = list(map(lambda e: (e, v_y - max_dist), max_dist_candidates_x))
    bottom_column = list(map(lambda e: (e, v_y + max_dist), max_dist_candidates_x))

    junction_pixels = dict()
    if tuple([u, v]) in edges_dictionary.keys():
        junction_pixels[tuple([u, v])] = edges_dictionary[tuple([u, v])]
    else:
        junction_pixels[tuple([u, v])] = edges_dictionary[tuple([v, u])]

    if tuple([v, w1]) in edges_dictionary.keys():
        junction_pixels[tuple([v, w1])] = edges_dictionary[tuple([v, w1])]
    else:
        junction_pixels[tuple([v, w1])] = edges_dictionary[tuple([w1, v])]

    if tuple([v, w2]) in edges_dictionary.keys():
        junction_pixels[tuple([v, w2])] = edges_dictionary[tuple([v, w2])]
    else:
        junction_pixels[tuple([v, w2])] = edges_dictionary[tuple([w2, v])]

    w1_in_radius = [i for i in left_column + right_column + top_column + bottom_column
                    if i in junction_pixels[(v, w1)]]
    if len(w1_in_radius) == 0:
        w1_in_radius = [w1]

    w2_in_radius = [i for i in left_column + right_column + top_column + bottom_column
                    if i in junction_pixels[(v, w2)]]
    if len(w2_in_radius) == 0:
        w2_in_radius = [w2]

    u_in_radius = [i for i in left_column + right_column + top_column + bottom_column
                   if i in junction_pixels[(u, v)]]
    if len(u_in_radius) == 0:
        u_in_radius = [u]

    return u_in_radius[0], w1_in_radius[0], w2_in_radius[0]


# ---------------------------------------------------------------------------------
# calculate edge t scores using local region only
#
def calculate_edge_scores_local(u, v, edge_dictionary, t_scores, max_dist):
    # print('u=', u, 'v=', v)
    junction_v_edges = [edge for edge in edge_dictionary
                        if (edge[0] == v and edge[1] != u) or (edge[0] != u and edge[1] == v)]
    # print(junction_v_edges)
    v_edges = [e[0] if e[1] == v else e[1] for e in junction_v_edges]
    for combination in it.combinations(v_edges, 2):
        w1, w2 = combination
        in_u, in_w1, in_w2 = get_nearby_pixels(u, v, w1, w2, edge_dictionary, max_dist=max_dist)
        uv_vw1 = calculate_abs_angle(in_u, v, in_w1)
        uv_vw2 = calculate_abs_angle(in_u, v, in_w2)
        w1v_vw2 = calculate_abs_angle(in_w1, v, in_w2)
        uv_bridge = np.abs(np.pi - w1v_vw2) + np.abs(np.pi / 2.0 - uv_vw1) + np.abs(np.pi / 2.0 - uv_vw2)
        vw1_bridge = np.abs(np.pi - uv_vw1) + np.abs(np.pi / 2.0 - uv_vw2) + np.abs(np.pi / 2.0 - w1v_vw2)
        vw2_bridge = np.abs(np.pi - uv_vw2) + np.abs(np.pi / 2.0 - uv_vw1) + np.abs(np.pi / 2.0 - w1v_vw2)
        t_scores[(u, v, w1, w2)] = [(u, v, uv_bridge), (v, w1, vw1_bridge), (v, w2, vw2_bridge)]


# ---------------------------------------------------------------------------------
# finds "best" out of local region angle and complete edge angle - for each edge
# totals 6 possible combinations
#
def calculate_edge_scores(u, v, edge_dictionary, t_scores, max_dist):
    junction_v_edges = [edge for edge in edge_dictionary
                        if (edge[0] == v and edge[1] != u) or (edge[0] != u and edge[1] == v)]
    v_edges = [e[0] if e[1] == v else e[1] for e in junction_v_edges]
    # print('edge=', edge)
    # print('junction=', junction_v_edges)
    # For each edge we check u,v v,w1 v,w2
    # other side below...
    for combination in it.combinations(v_edges, 2):
        w1, w2 = combination
        # get coordinates in radius 9 - then calculate angle
        in_u, in_w1, in_w2 = get_nearby_pixels(u, v, w1, w2, edge_dictionary, max_dist=max_dist)
        # print('in_u=', in_u, 'in_w1=', in_w1,'v=', v, 'in_w2=', in_w2)
        u_s = [u, in_u]
        w1_s = [w1, in_w1]
        w2_s = [w2, in_w2]
        uv_vw1 = [calculate_abs_angle(one_u, v, one_w1) for one_u in u_s for one_w1 in w1_s]
        uv_vw2 = [calculate_abs_angle(one_u, v, one_w2) for one_u in u_s for one_w2 in w2_s]
        w1v_vw2 = [calculate_abs_angle(one_w1, v, one_w2) for one_w1 in w1_s for one_w2 in w2_s]
        uv_bridge = np.min([np.abs(np.pi - one_w1v_vw2) + np.abs(np.pi / 2.0 - one_uv_vw1) +
                            np.abs(np.pi / 2.0 - one_uv_vw2) for one_w1v_vw2 in w1v_vw2
                            for one_uv_vw1 in uv_vw1 for one_uv_vw2 in uv_vw2])
        vw1_bridge = np.min([np.abs(np.pi - one_uv_vw1) + np.abs(np.pi / 2.0 - one_uv_vw2) +
                             np.abs(np.pi / 2.0 - one_w1v_vw2) for one_uv_vw1 in uv_vw1
                             for one_uv_vw2 in uv_vw2 for one_w1v_vw2 in w1v_vw2])
        vw2_bridge = np.min([np.abs(np.pi - one_uv_vw2) + np.abs(np.pi / 2.0 - one_uv_vw1) +
                             np.abs(np.pi / 2.0 - one_w1v_vw2) for one_uv_vw2 in uv_vw2
                             for one_uv_vw1 in uv_vw1 for one_w1v_vw2 in w1v_vw2])
        t_scores[(u, v, w1, w2)] = [(u, v, uv_bridge), (v, w1, vw1_bridge), (v, w2, vw2_bridge)]


# ---------------------------------------------------------------------------------
# calculate_junctions_t_scores
def calculate_junctions_t_scores(edge_dictionary, skeleton, file_name, image_preprocessed):
    time_print('calculating t scores ...')
    t_scores = dict()
    for edge in edge_dictionary:
        u, v = edge
        calculate_edge_scores(u, v, edge_dictionary, t_scores, max_dist=7)
        calculate_edge_scores(v, u, edge_dictionary, t_scores, max_dist=7)

    # in greedy manner: find junction in t_scores where u,v v,w1 v,w2 has minimum T score
    # mark u,v as Bridge
    # mark v,w1 and v,w2 as Link
    # TODO OPTION 1 - 100% greedy - and remove conflicts on the go
        # remove all u,v from t_scores marked as L
        # remove all v,w1 and v,w2 from t_scores marked as B
    # TODO OPTION 2 - each time check for conflicts, and mark as such
        # add junction to B and L lists
        # check whether new min junction
    bridges = set()
    links = set()
    time_print('greedy manner labeling ...')
    index = 1
    time_print('start=' + str(len(t_scores)))
    while t_scores:
        if index % 500 == 0:
            time_print(len(t_scores))
        # else:
        #     print(len(t_scores), end=' ')
        index += 1
        # find minimum score for each junction
        min_t_scores = dict()
        for key in t_scores.keys():
            min_score_index = np.argmin(map(lambda e_1, e_2, score: score, t_scores[key]))
            min_t_scores[key] = t_scores[key][min_score_index]

        # print(min_t_scores.values())
        # find junction with minimum score of all junctions
        values = [value[2] for value in min_t_scores.values()]
        min_score_index = np.argmin(values)
        min_score_key = list(min_t_scores.keys())[min_score_index]
        min_score = min_t_scores[min_score_key]
        # print('min_score_index=', min_score_index, 'min_score_key=', min_score_key, 'min_score=', min_score)
        # add to bridges - CHECK FOR CONFLICT
        new_bridge = (min_score[0], min_score[1])
        if new_bridge not in edge_dictionary.keys():
            p1, p2 = new_bridge
            new_bridge = (p2, p1)

        # print('t_scores[min_score_key]=', t_scores[min_score_key])
        # add to links - CHECK FOR CONFLICT
        two_links = [item for item in t_scores[min_score_key] if item is not min_score]
        # print('two_links=', two_links)
        # add new links to links set

        if new_bridge not in links:
            bridges.add(new_bridge)
            for link in two_links:
                e1, e2, _ = link
                new_link = (e1, e2)
                if new_link not in edge_dictionary.keys():
                    new_link = (e2, e1)
                links.add(new_link)
        # check for conflicts before adding them??
        # add new bridge to bridges set
        # remove minimum t score junction from t_scores
        t_scores.pop(min_score_key)
        # print('B=', bridges, 'L=', links)
    print()
    skeleton = skeleton.astype(np.uint8)
    # draw_graph_edges(edge_dictionary, skeleton, 'before')
    image = cv2.cvtColor(np.zeros_like(skeleton), cv2.COLOR_GRAY2RGB)
    image = draw_edges(bridges, edge_dictionary, image, (255, 0, 0))
    image = draw_edges(links, edge_dictionary, image, (0, 255, 0))
    rest = [x for x in edge_dictionary.keys() if x not in set(bridges).union(links)]
    image = draw_edges(rest, edge_dictionary, image, (0, 0, 255))

    cv2.imwrite('./' + file_name + '/classifications.png', image)

    # cv2.namedWindow('after')
    # cv2.imshow('after', image)
    # cv2.namedWindow('r')
    # cv2.imshow('r', image_preprocessed)
    # cv2.waitKey()
    # cv2.destroyAllWindows()
    image_preprocessed = cv2.cvtColor(image_preprocessed, cv2.COLOR_GRAY2RGB)
    image_preprocessed = draw_edges(bridges, edge_dictionary, image_preprocessed, (255, 0, 0))
    image_preprocessed = draw_edges(links, edge_dictionary, image_preprocessed, (0, 255, 0))
    # rest = [x for x in edge_dictionary.keys() if x not in set(bridges).union(links)]
    image_preprocessed = draw_edges(rest, edge_dictionary, image_preprocessed, (0, 0, 255))
    cv2.imwrite('./' + file_name + '/overlayed_classifications.png', image_preprocessed)
    # cv2.waitKey()
    # cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------
# main execution function
def execute(input_path):
    # retrieve list of images
    images = [f for f in listdir(input_path) if isfile(join(input_path, f))]
    i = 1
    for image in images:
        file_name = image.split('.')[0]
        print('[' + str(i) + '/' + str(len(images)) + ']', file_name)
        # pre-process image
        time_print('pre-process image...')
        image_preprocessed = pre_process(input_path + image)
        # create dir for results
        os.mkdir('results/' + file_name)
        file_name = 'results/' + file_name
        # extract ridges
        time_print('extract ridges, junctions...')
        # ridges_mask, ridges_matrix = ridge_extraction(image_preprocessed)
        skeleton, edge_dictionary = ridge_extraction(image_preprocessed, file_name)



        # mark junction pixels
        # time_print('mark junction pixels...')
        # junction_pixels_mask = mark_junction_pixels(ridges_mask)
        # cv2.imwrite('junction_pixels_mask.png', overlay_images(ridges_mask*255, junction_pixels_mask*255))
        # retrieve vertex pixels
        # time_print('retrieve vertex pixels...')
        # vertexes_dictionary, vertexes_list, labels, vertex_mask = get_vertexes(ridges_matrix, junction_pixels_mask)
        # save_image_like(ridges_mask, vertexes_list, 'vertex_mask')
        # retrieve edges between two vertexes
        # each edge value is a list of pixels from vertex u to vertex v
        # each edge key is a pair of vertexes (u, v)
        # time_print('retrieve edges between two vertexes...')
        # edge_dictionary = get_edges_between_vertexes(edges, degrees)
        # edge_dictionary = get_edges(ridges_mask, junction_pixels_mask, vertexes_list)
        # time_print('clean graph up...')
        # edge_dictionary = clean_graph(edge_dictionary, ridges_mask)
        # using each two vertexes of an edge, we classify whether an edge is a brige (between two lines),
        # or a link (part of a line). As a result, we receive a list of edges and their classification
        # time_print('classify edges...')
        # edge_scores = classify_edges(edge_dictionary, ridges_mask)
        # TODO ...
        # calculate for each junction its B L L, L B L, L L B values using distance from T shape
        # in greedy manner -
        #   choose the assignment with minimum value for u,v,w - for all junctions for every combination
        # TODO step 1: for each u,v v,w1 v,w2 JUNCTION -> calculate 3 scores: L L B, L B L, L L B distance from T
        image_preprocessed[image_preprocessed == 1] = 2
        image_preprocessed[image_preprocessed == 0] = 1
        image_preprocessed[image_preprocessed == 2] = 0
        calculate_junctions_t_scores(edge_dictionary, skeleton, file_name, image_preprocessed * 255)
        # TODO step 2: visualize result -> for each edge: if all B GREEN, if all L BLUE, mixed RED
        #
        # TODO step 3: some options (depending on result in step 2)
        #       TODO 3.1: for each edge that has no agreement we try to improve by choosing one of the two

        # TODO current work . . . combine edges
        # time_print('calculate vertex T-scores...')
        # calculate_junction_t_distances(vertexes_list, edge_dictionary, ridges_mask)
        # combined_edge_dictionary = combine_edges(vertexes_list, edge_dictionary, ridges_mask)
        # after_ridge_mask = cv2.cvtColor(np.zeros_like(ridges_mask), cv2.COLOR_GRAY2RGB)
        # for edge_list in combined_edge_dictionary.values():
        #    colors = []
        #    random_color = (rd.randint(50, 255), rd.randint(50, 255), rd.randint(50, 255))
        #    while random_color in colors:
        #        random_color = (rd.randint(50, 255), rd.randint(50, 255), rd.randint(50, 255))
        #    after_ridge_mask = overlay_edges(after_ridge_mask, edge_list, random_color)
        #    colors.append(random_color)
        # cv2.imwrite(file_name + '_result.png', after_ridge_mask)
        # cv2.namedWindow('before')
        # cv2.namedWindow('after')
        # cv2.imshow('before', before_ridge_mask)
        # cv2.imshow('after', after_ridge_mask)
        # cv2.waitKey()
        # cv2.destroyAllWindows()

        # classified_image = overlay_classified_edges(image_preprocessed, edge_dictionary, edge_scores)
        # time_print('combine link edges...')

        # cv2.imshow('overlay_classified_edges', classified_image)
        # cv2.imwrite(input_path + '/results/' + file_name + '_result.png', classified_image)
        # save the graph in a file
        # with open(input_path + '/results/' + file_name + '_graph.pkl', 'wb') as handle:
        #     pickle.dump(edge_dictionary, handle, protocol=pickle.HIGHEST_PROTOCOL)
        # save classifications of each edge in a file
        # with open(input_path + '/results/' + file_name + '_scores.pkl', 'wb') as handle:
        #     pickle.dump(edge_scores, handle, protocol=pickle.HIGHEST_PROTOCOL)
        i += 1
        # cv2.waitKey()
        # cv2.destroyAllWindows()

        # display
        # overlay_image = overlay_images(ridges_mask * 255, vertex_mask * 255, vertexes_list)
        # cv2.imwrite('overlay_image.png', overlay_image)
        # cv2.imshow('overlay_image', overlay_image)
        # cv2.waitKey()
        # cv2.destroyAllWindows()


if __name__ == "__main__":
        execute("./data/original/")
