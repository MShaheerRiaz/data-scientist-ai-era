import type { INodeProperties } from 'n8n-workflow';

export const instagramFields: INodeProperties[] = [
	{
		displayName: 'Media Type',
		name: 'mediaType',
		type: 'options',
		options: [
			{ name: 'Image', value: 'IMAGE', description: 'Single image post' },
			{ name: 'Reel', value: 'REELS', description: 'Short video reel' },
			{ name: 'Video', value: 'VIDEO', description: 'Regular video post' },
		],
		default: 'IMAGE',
		required: true,
	},
	{
		displayName: 'Media URL',
		name: 'mediaUrl',
		type: 'string',
		default: '',
		required: true,
		description: 'Publicly accessible URL of the image or video file',
		placeholder: 'https://example.com/image.jpg',
	},
	{
		displayName: 'Caption',
		name: 'caption',
		type: 'string',
		typeOptions: { rows: 4 },
		default: '',
		description: 'Caption for the post (supports hashtags and @mentions)',
	},
];
