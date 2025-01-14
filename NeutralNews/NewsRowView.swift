//
//  NewsRowView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct NewsRowView: View {
    let news: News
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(news.category.uppercased())
                Text(news.pubDate.uppercased())
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .lineLimit(1)
            
            Text(news.title)
                .font(.headline)
                .lineLimit(3)
            
            AsyncImage(url: URL(string: news.imageUrl!)) { image in
                image.image?
                    .resizable()
                    .scaledToFit()
            }
            .frame(maxWidth: .infinity)
            .clipShape(.rect(cornerRadius: 20))
            
            Text(news.description)
                .foregroundStyle(.secondary)
                .lineLimit(5)
                .padding(.top, 8)
            
            MediaCircleView(media: news.sourceMedium)
                .padding(.top, 8)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(.regularMaterial)
        .clipShape(.rect(cornerRadius: 20))
        .padding(.horizontal)
    }
}

#Preview {
    NewsRowView(news: News.mock)
}
