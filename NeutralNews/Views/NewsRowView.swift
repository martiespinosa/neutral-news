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
                Spacer()
                Text(String(news.pubDate.toDate()?.formatted(date: .abbreviated, time: .omitted) ?? ""))
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .lineLimit(1)
            
            Text(news.title)
                .font(.headline)
                .lineLimit(3)
            
            NewsImageView(news: news)
            
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

struct NewsImageView: View {
    let news: News
    
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .bottom) {
                AsyncImage(url: URL(string: news.imageUrl ?? "")) { phase in
                    if let image = phase.image {
                        image
                            .resizable()
                            .scaledToFill()
                            .frame(width: geometry.size.width, height: 250)
                            .clipped()
                    } else {
                        ShimmerView()
                            .frame(width: geometry.size.width, height: 250)
                    }
                }
                
                Rectangle()
                    .fill(.ultraThinMaterial)
                    .frame(height: 180)
                    .mask(
                        LinearGradient(
                            gradient: Gradient(colors: [
                                Color.black.opacity(0),
                                Color.black.opacity(0.2),
                                Color.black.opacity(0.8),
                                Color.black.opacity(0.9),
                                Color.black.opacity(1)
                            ]),
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                
                Text(news.title)
                    .padding(.horizontal, 12)
                    .padding(.vertical)
                    .font(.system(size: 22, design: .serif))
//                    .font(.title2)
                    .fontWeight(.semibold)
//                    .foregroundStyle(.nnForeground)
                    .foregroundStyle(.white)
                    .lineLimit(3)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(width: geometry.size.width)
        }
        .frame(height: 250)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}
