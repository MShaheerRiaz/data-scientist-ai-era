import type { INodeProperties } from 'n8n-workflow';

export const linkedInFields: INodeProperties[] = [
	{
		displayName: 'Post Type',
		name: 'postType',
		type: 'options',
		options: [
			{ name: 'Text', value: 'NONE', description: 'Text-only post' },
			{ name: 'Article / Link', value: 'ARTICLE', description: 'Share a link with preview' },
		],
		default: 'NONE',
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
		displayName: 'Article URL',
		name: 'articleUrl',
		type: 'string',
		default: '',
		required: true,
		displayOptions: { show: { postType: ['ARTICLE'] } },
		placeholder: 'https://example.com/article',
	},
	{
		displayName: 'Article Title',
		name: 'articleTitle',
		type: 'string',
		default: '',
		displayOptions: { show: { postType: ['ARTICLE'] } },
	},
	{
		displayName: 'Article Description',
		name: 'articleDescription',
		type: 'string',
		default: '',
		displayOptions: { show: { postType: ['ARTICLE'] } },
	},
];
