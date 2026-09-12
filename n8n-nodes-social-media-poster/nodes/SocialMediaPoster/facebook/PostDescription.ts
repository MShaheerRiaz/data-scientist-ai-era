import type { INodeProperties } from 'n8n-workflow';

export const facebookFields: INodeProperties[] = [
	{
		displayName: 'Page ID',
		name: 'pageId',
		type: 'string',
		default: '',
		required: true,
		hint: 'The numeric Facebook Page ID to post to (found in Page → About → Page Transparency)',
	},
	{
		displayName: 'Post Type',
		name: 'postType',
		type: 'options',
		options: [
			{ name: 'Text', value: 'text', description: 'Text-only post' },
			{ name: 'Photo', value: 'photo', description: 'Post with an image from a URL' },
			{ name: 'Link', value: 'link', description: 'Post with a link preview' },
		],
		default: 'text',
	},
	{
		displayName: 'Message',
		name: 'message',
		type: 'string',
		typeOptions: { rows: 4 },
		default: '',
		required: true,
		description: 'The text content of the post',
	},
	{
		displayName: 'Photo URL',
		name: 'photoUrl',
		type: 'string',
		default: '',
		required: true,
		displayOptions: { show: { postType: ['photo'] } },
		description: 'Publicly accessible URL of the image to post',
		placeholder: 'https://example.com/image.jpg',
	},
	{
		displayName: 'Link URL',
		name: 'linkUrl',
		type: 'string',
		default: '',
		required: true,
		displayOptions: { show: { postType: ['link'] } },
		placeholder: 'https://example.com/article',
	},
];
