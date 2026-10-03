import type { INodeProperties } from 'n8n-workflow';

export const threadsFields: INodeProperties[] = [
	{
		displayName: 'Media Type',
		name: 'mediaType',
		type: 'options',
		options: [
			{ name: 'Text', value: 'TEXT', description: 'Text-only post' },
			{ name: 'Image', value: 'IMAGE', description: 'Post with an image' },
			{ name: 'Video', value: 'VIDEO', description: 'Post with a video' },
		],
		default: 'TEXT',
		required: true,
	},
	{
		displayName: 'Text',
		name: 'text',
		type: 'string',
		typeOptions: { rows: 4 },
		default: '',
		description: 'Text content of the post',
	},
	{
		displayName: 'Media URL',
		name: 'mediaUrl',
		type: 'string',
		default: '',
		required: true,
		displayOptions: { show: { mediaType: ['IMAGE', 'VIDEO'] } },
		description: 'Publicly accessible URL of the image or video',
		placeholder: 'https://example.com/image.jpg',
	},
];
