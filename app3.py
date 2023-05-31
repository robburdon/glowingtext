import streamlit as st
import bpy
from mathutils import Vector
import uuid
from  PIL import Image
import numpy as np

def create_text_object(text, location, scale):
	bpy.ops.object.text_add(enter_editmode=False, align='WORLD', location=location, scale=scale)
	text_object = bpy.context.object
	text_object.data.body = text
	text_object.scale = scale # the scale parameter in the text_add() function does not seem to work so this must be duplicated here
	fnt = bpy.data.fonts.load('./FreeSansBoldOblique.ttf')
	text_object.data.font = fnt
	return text_object


def center_text(text_obj):
	bpy.context.view_layer.update()
	text_dimensions = text_obj.dimensions
	text_obj.location.x -= text_dimensions.x / 2
	text_obj.location.y -= text_dimensions.y / 2


def create_camera(location, target=None):
	bpy.ops.object.camera_add(location=location)
	camera = bpy.context.active_object
	if target is None:
	    camera.rotation_euler=(0.0, 0.0, 0.0)
	else:
	    constraint = camera.constraints.new(type='TRACK_TO')
	    constraint.target = target
	    constraint.track_axis = 'TRACK_NEGATIVE_Z'
	    constraint.up_axis = 'UP_Y'

	return camera

#unnecessary as setting up render nodes generates a background.
def setup_background_image(camera, filepath):
	img = bpy.data.images.load(filepath)
	camera.data.show_background_images = True
	bg = camera.data.background_images.new()
	bg.image = img
	bg.frame_method = 'FIT'
	bg.alpha = 1.0
	return bg
	
def pil_to_image(pil_image, name='NewImage'):
	'''
	PIL image pixels is 2D array of byte tuple (when mode is 'RGB', 'RGBA') or byte (when mode is 'L')
	bpy image pixels is flat array of normalized values in RGBA order
	'''
	# setup PIL image conversion
	width = pil_image.width
	height = pil_image.height
	byte_to_normalized = 1.0 / 255.0
	# create new image
	bpy_image = bpy.data.images.new(name, width=width, height=height)

	# convert Image 'L' to 'RGBA', normalize then flatten 
	bpy_image.pixels[:] = (np.asarray(pil_image.convert('RGBA'),dtype=np.float32) * byte_to_normalized).ravel()

	return bpy_image


def setup_eevee_bloom(bloom_intensity):
	bpy.context.scene.render.engine = 'BLENDER_EEVEE'
	bpy.context.scene.eevee.use_bloom = True
	bpy.context.scene.eevee.bloom_intensity = bloom_intensity


def create_emission_material(name, color, strength):
	mat = bpy.data.materials.new(name=name)
	mat.use_nodes = True
	mat.node_tree.nodes.clear()
	emission_node = mat.node_tree.nodes.new("ShaderNodeEmission")
	emission_node.inputs["Color"].default_value = color
	emission_node.inputs["Strength"].default_value = strength
	output_node = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
	mat.node_tree.links.new(emission_node.outputs[0], output_node.inputs[0])
	return mat


def setup_render_nodes(img):
	bpy.context.scene.use_nodes = True
	
	scene = bpy.context.scene
	nodetree = bpy.context.scene.node_tree

	node_alpha = nodetree.nodes.new("CompositorNodeAlphaOver")
	node_image = nodetree.nodes.new("CompositorNodeImage")
	node_scale = nodetree.nodes.new("CompositorNodeScale")
	node_lensdist = nodetree.nodes.new("CompositorNodeLensdist")

	node_scale.space = 'RENDER_SIZE'
	node_scale.frame_method = 'FIT'
	#node_lensdist.dispersion = 0.2
	node_image.image = img

	nodetree.links.new(node_image.outputs["Image"], node_scale.inputs[0])
	nodetree.links.new(node_scale.outputs["Image"], node_alpha.inputs[1])
	nodetree.links.new(node_alpha.outputs["Image"], nodetree.nodes["Composite"].inputs[0])
	nodetree.links.new(nodetree.nodes["Render Layers"].outputs["Image"], node_alpha.inputs[2])


def setup_render_nodes_distortion(img, dispersion_factor):

	bpy.context.scene.use_nodes = True

	scene = bpy.context.scene
	nodetree = bpy.context.scene.node_tree

	#bpy.context.area.ui_type = 'CompositorNodeTree'
	bpy.context.scene.use_nodes = True

	scene = bpy.context.scene
	nodetree = bpy.context.scene.node_tree

	#add alpha
	node1 = nodetree.nodes.new("CompositorNodeMixRGB")
	bpy.data.scenes["Scene"].node_tree.nodes["Mix"].blend_type = 'LIGHTEN'

	#add image

	node2 = nodetree.nodes.new("CompositorNodeImage")

	#add distortion node

	node3 = nodetree.nodes.new("CompositorNodeScale")

	#distortion node settings
	bpy.data.scenes["Scene"].node_tree.nodes["Scale"].space = 'RENDER_SIZE'
	bpy.data.scenes["Scene"].node_tree.nodes["Scale"].frame_method = 'FIT'

	#lens distortion
	node4 = nodetree.nodes.new("CompositorNodeLensdist")
	bpy.data.scenes["Scene"].node_tree.nodes["Lens Distortion"].inputs[2].default_value = dispersion_factor # this is dispersion factor

	####conections
	nodetree.links.new(node2.outputs["Image"],node3.inputs[0])
	nodetree.links.new(node3.outputs["Image"],node1.inputs[1])
	nodetree.links.new(node1.outputs["Image"],nodetree.nodes["Composite"].inputs[0])
	nodetree.links.new(nodetree.nodes["Render Layers"].outputs["Image"],node4.inputs[0])
	nodetree.links.new(node4.outputs["Image"],node1.inputs[2])
	
	#background image
	nodetree.nodes["Image"].image = img

def remove_objects(*object_names):
	bpy.ops.object.select_all(action='DESELECT')
	for object_name in object_names:
	    if object_name in bpy.data.objects:
	        bpy.data.objects[object_name].select_set(True)
	bpy.ops.object.delete()


def render_scene(cam, filepath):
	scene = bpy.context.scene
	
	# add camera to scene
	scene.camera=cam
	
	#render settings
	scene.render.image_settings.file_format='PNG'
	#bpy.context.scene.render.image_settings.compression = 15
	bpy.context.scene.eevee.taa_render_samples = 16
	scene.render.filepath = filepath
	bpy.ops.render.render(write_still=1)
	return filepath  # Return filepath to display it after rendering

def main(input_top_text, input_bottom_text, text_location_scale_y, bloom_intensity, hex_color, use_dispersion, dispersion_factor, input_filepath, uploaded_file):

	#clear the scene
	bpy.ops.wm.read_homefile(use_empty=True)
	remove_objects('Cube', 'Camera')
	
	#setup text
	top_text = create_text_object(input_top_text, (0, text_location_scale_y, 0), (text_scale, text_scale, text_scale))
	center_text(top_text)
	bottom_text = create_text_object(input_bottom_text, (0, -text_location_scale_y, 0), (text_scale, text_scale, text_scale))
	center_text(bottom_text)
	
	#setup camera
	camera_location = (0, 0, 20)
	camera = create_camera(camera_location, None)

	#setup_background_image(camera, input_filepath) --not necessary due to compositing/nodes setup
	if uploaded_file is not None:
		image = Image.open(uploaded_file)
		#image = image.rotate(30)  #--this line should be before it becomes a blender image format
		bpy_image = pil_to_image(image, name='NewImage')
		#bpy_
	else:
		bpy_image = bpy.data.images.load(input_filepath)
		
	def hex_to_rgb(hexa):
		return tuple(int(hexa[i:i+2], 16)  for i in (0, 2, 4))

	rgb_color = hex_to_rgb(hex_color[1:])
	material = create_emission_material('EmiMat', (rgb_color[0], rgb_color[1], rgb_color[2], 1), 0.05)  # nice purple = (0.151736, 0.0997155, 1, 1)
	top_text.data.materials.append(material)
	bottom_text.data.materials.append(material)
	
	
	#setup scene, bloom, and render nodes
	bpy.context.scene.render.film_transparent = True
	setup_eevee_bloom(bloom_intensity)
	if use_dispersion:
		setup_render_nodes_distortion(bpy_image, dispersion_factor)
	else:
		setup_render_nodes(bpy_image)

	# Generate a unique file path for the output image
	output_filepath = f'./output/image_{uuid.uuid4()}.png'
	
	# Here is the call to render the scene
	rendered_image_path = render_scene(camera, output_filepath)
	
	return rendered_image_path  # Return the path to the rendered image

# In place of if __name__ == "__main__":, setup the Streamlit interface
input_top_text = st.text_input('Top text', 'top text')
input_bottom_text = st.text_input('Bottom text', 'bottom text')
text_location_scale_y = st.slider('Location Y Scale', min_value=0.0, max_value=5.0, value=3.0, step=0.1)
text_scale = st.slider('Text Scale', min_value=0.1, max_value=5.0, value=1.0, step=0.1)  # Added this line
bloom_intensity = st.slider('Bloom intensity', min_value=0.0, max_value=1.0, value=0.1, step=0.01)
dispersion_factor = st.slider('Dispersion', min_value=0.0, max_value=0.5, value=0.1, step=0.01)
use_dispersion = st.checkbox('Use dispersion mode')
color = st.color_picker('Text Color', '#321996')


input_filepath = st.text_input('File path', './PXL_20230318_153852831.jpg')

uploaded_file = st.file_uploader("Choose a file",type=['png', 'jpeg', 'jpg'])
		
placeholder = st.empty()

if st.button('Render'):
	#terrible but works
	rendered_image_path = main(input_top_text, input_bottom_text, text_location_scale_y, bloom_intensity, color, use_dispersion, dispersion_factor, input_filepath, uploaded_file)

	# Display the rendered image
	placeholder = st.image(rendered_image_path)

